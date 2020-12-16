import abc
import sys
import platform
import uuid
from .abstract import Controller, handler
from smaug_iot.nfc.messages import Announce, Echo, EchoSuccess, \
    Verify, VerifySuccess, VerifyFailure, \
    Open, OpenSuccess, OpenFailure, \
    Close, CloseSuccess, CloseFailure, \
    Query, QuerySuccess, QueryFailure
from smaug_iot.nfc.comm import Nfc
import threading
import logging
import asyncio
import concurrent
import time
from .access import AccessSchema


# stab at a bit more generic async wrapper...
class Picket(object):
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.event = asyncio.Event()
        self.result = None

    def complete(self, result):
        self.result = result
        self.event.set()


class Fence(object):
    class result(object):
        def __init__(self, ok, result=None, error=None):
            self.ok = ok
            self.result = result
            self.error = error

        def __bool__(self):
            return self.ok

        def __str__(self):
            if (self.ok):
                return f"ok<{self.result!r}>"
            else:
                return f"fail<{self.error}>"

        __repr__ = __str__

    def complete(self, id, result):
        if id not in self.requests:
            return

        self.requests[id].complete(result)

    def __init__(self, timeout=60):
        self.timeout = timeout
        self.requests = {}
        self.log = logging.getLogger(self.__class__.__name__)

    async def fire(self, action, null=None, timeout=None):
        """Call action with the given timeout (or default from constructor if
not given), and returns a RESULT object which evaluates to False if
there was a failure or a timeout, and True if there is a successfull
result.

The result object has fields .value on success, and .error on error."""

        timeout = self.timeout if timeout is None else timeout

        call = Picket()
        assert call.id not in self.requests
        self.requests[call.id] = call
        await action(call)
        try:
            start = time.time()
            await asyncio.wait_for(action(call), timeout)
            left = max(0, timeout, timeout - (time.time() - start))
            await asyncio.wait_for(call.event.wait(), left)
            total = time.time() - start
            # TODO: check exception status!
            self.log.debug("%s: Finished: call %ss, wait %ss, total %ss: %r",
                           call.id, timeout - left, total - (timeout - left),
                           total, call.result)
            return Fence.result(True, result=call.result)
        except asyncio.TimeoutError as err:
            self.log.debug("%s: Operation %r timeouted (timeout=%r)",
                           call.id, action, timeout)
            return Fence.result(False, result=null, error=str(err))
        finally:
            del self.requests[call.id]


class NfcController(Controller):
    def __init__(self, args):
        super().__init__(args)
        self.nfc_device = args.nfc_device
        self.dummy_lock = args.dummy_lock
        self.running = False
        self.stopped = threading.Event()
        self.nfc = None
        self.fence = Fence()
        self.was_open = True
        self.reset()

        self.announce = Announce(
            locker_id=args.locker_id,
            contract_address=args.contract_address,
            name=args.locker_name,
            image_urls=args.locker_image_url,
            open_close_type=args.locker_open_close_type)

    def reset(self):
        self.has_access = False
        self.allowed_ops = []
        # we can cache the lock open state locally pretty
        # aggressively, as we reset the state for each new connetion
        self.is_open = None

    @classmethod
    def augment_parser(cls, parser):
        parser.add_argument('--nfc-device', type=str,
                            default="tty:ttyS0:pn532",
                            help="nfcpy device (default tty:serial0:pn542)")
        parser.add_argument('--locker-id',
                            default=platform.node(),
                            help='Locker identifier to announce')
        parser.add_argument('--contract-address',
                            default="dummy-address",
                            help='Contract address to announce')
        parser.add_argument('--locker-name',
                            default='Smart locker',
                            help='Descriptive name for the locker')
        parser.add_argument('--locker-image-url',
                            default=[],
                            action='append',
                            help=('Locker image URL, may be specified more '
                                  'than once, '
                                  'the first one is becomes the '
                                  'primary image'))
        parser.add_argument('--locker-open-close-type',
                            default='open-tap-close',
                            choices=('open-tap-close', 'open-push-close',
                                     'open-delay-push-close'),
                            help='Open and closing type')
        parser.add_argument('--dummy-lock',
                            default=False, action='store_true',
                            help=("Do not use the real "
                                  "lock controller, fake it"))

    # Handlers for different message types
    async def handle_echo(self, r):
        self.log.debug(f"Echo, replying back")
        return EchoSuccess(message=r.message)

    @handler("/access_result", AccessSchema())
    async def access_result(self, id, allowed, actions, **kwargs):
        self.log.debug("got access result: id=%r allowed=%r actions=%r",
                       id, allowed, actions)
        self.fence.complete(id, (allowed, None, actions))

    async def handle_verify(self, r):
        self.log.debug(f"Verify: token={r.token}")
        # in reality, we would need to send a message to token
        # controller, wait for response (with timeout), then send
        # response back --- and all of that in another thread,
        # probably

        async def query(call):
            self.publish(
                "/access",
                AccessSchema().dumps({
                    "id": call.id,
                    "token": r.token,
                    "actions": []
                }),
                response_topic="/access_result")

        result = await self.fence.fire(query, (False, "unknown error", []))

        self.log.info(
            "Verified token %r: %s = %s",
            r.token,
            "SUCCESS" if result else "FAILURE",
            (f"VALID for {', '.join(result.result[2])}" if result.result[0]
             else "INVALID") if result
            else result.error or "-" )

        if not result:
            return VerifyFailure(
                message=result.error or "Failed to check authentication oken")

        if not result.result[0]:
            return VerifyFailure(
                message=(result.result[1]
                         or "Invalid or expired authentication token"))

        self.has_access = True
        self.allowed_ops = result.result[2]
        return VerifySuccess()

    @handler("/lock_result", int)
    async def lock_result(self, locked):
        self.log.debug("got lock result: locked=%r", locked)
        self.fence.complete(self.lock_query_id, locked)

    async def refresh_lock_state(self):
        self.log.debug("refresh_lock_state: is_open=%r", self.is_open)

        if self.dummy_lock:
            self.is_open = self.was_open
        elif self.is_open is None:
            self.log.debug("need to query state from lock")

            async def query(call):
                self.lock_query_id = call.id  # baaaad
                self.publish("/lock/state", response_topic="/lock_result")

            result = await self.fence.fire(query, None, timeout=1)
            self.is_open = False if result.result else True

        self.log.info("Queried lock: %s", "OPEN" if self.is_open else "CLOSED")

        return (True, None)

    async def set_lock_locked(self, locked):
        if not self.dummy_lock:
            self.publish("/lock", 1 if locked else 0)

        self.is_open = not locked
        self.was_open = self.is_open

        return True, None

    def state_if_allowed(self):
        if self.has_access and 'state' in self.allowed_ops:
            return {'state': 'open' if self.is_open else 'closed'}
        return {}

    async def handle_query(self, r):
        if not self.has_access:
            return QueryFailure(message='Authentication missing or invalid')

        if 'state' not in self.allowed_ops:
            return QueryFailure(message='Query operation not allowed')

        ok, err = await self.refresh_lock_state()

        if not ok:
            return QueryFailure(message=(err or "failed checking the lock"))

        return QuerySuccess(**self.state_if_allowed())

    async def handle_open(self, r):
        if not self.has_access:
            return OpenFailure(message='Authentication missing or invalid')

        if 'unlock' not in self.allowed_ops:
            return OpenFailure(message='Open operation not allowed',
                               **self.state_if_allowed())

        ok, err = await self.set_lock_locked(False)

        if not ok:
            return OpenFailure(message=(err or "Failed operating the lock"),
                               **self.state_if_allowed())

        self.log.info("Changed state: UNLOCKED")

        return OpenSuccess(state='open' if self.is_open else 'closed')

    async def handle_close(self, r):
        if not self.has_access:
            return CloseFailure(message='Authentication missing or invalid')

        if 'lock' not in self.allowed_ops:
            return CloseFailure(message='Close operation not allowed',
                                **self.state_if_allowed())

        ok, err = await self.set_lock_locked(True)

        if not ok:
            return CloseFailure(message=(err or "Failed operating the lock"),
                                **self.state_if_allowed())

        self.log.info("Changed state: LOCKED")

        return CloseSuccess(state='open' if self.is_open else 'closed')

    # This is the actual meat of the NFC controller where it, after
    # having established NFC communication with initiator, performs
    # bidirectional communication with the other device.
    def communicate(self, loop):
        self.reset()

        # We start by sending announce record informing the other end
        # about what and who we are.

        self.log.debug("Sending announce: %r", self.announce)
        request = self.nfc.send(self.announce)

        async def handle(request):
            if isinstance(request, Echo):
                return await self.handle_echo(request)
            if isinstance(request, Verify):
                return await self.handle_verify(request)
            if isinstance(request, Query):
                return await self.handle_query(request)
            if isinstance(request, Open):
                return await self.handle_open(request)
            if isinstance(request, Close):
                return await self.handle_close(request)

            return None

        while request is not None:
            self.log.debug(f"Request: {request}")

            start = time.time()
            reply = asyncio.run_coroutine_threadsafe(
                handle(request), loop).result()
            end = time.time()

            self.log.debug("reply in %fs: %r", end - start, reply)

            if reply is None:
                self.log.debug("Nothing to reply back, disconnecting")
                break

            self.log.debug(f"Replying with {reply}: {reply.encode().hex()}")
            request = self.nfc.send(reply)

    def initialize(self):
        self.log.debug("contacting NFC device: %r", self.nfc_device)

        self.nfc = Nfc(self.nfc_device, timeout=5)
        self.log.debug("nfc=%r", self.nfc)

        loop = asyncio.get_running_loop()

        # inner function, don't move this to class method
        def connect():
            try:
                while self.running:
                    if self.nfc.listen():
                        self.log.debug("NFC initiator detected, "
                                       "starting communication")
                        try:
                            self.communicate(loop)
                        except:
                            self.log.exception("Communication failed")
                    else:
                        self.log.debug("Listen timeout, looping")
            finally:
                self.log.debug("no more running, stopping")
                self.running = False
                self.stopped.set()

        self.running = True
        self.stopped.clear()

        thread = threading.Thread(target=connect)
        self.log.debug("starting connect thread=%r with loop=%r", thread, loop)
        thread.start()

        # logging.getLogger("nfc.clf").setLevel(logging.DEBUG)

    def uninitialize(self):
        self.log.debug("Stopping NFC")
        if self.nfc:
            self.nfc.close()

        if self.running:
            self.running = False
            self.stopped.wait()
