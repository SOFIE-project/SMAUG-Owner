import abc
import sys
from .abstract import Controller, handler, Response
try:
    wiringpi = None
    import wiringpi
except ImportError:
    pass


class AbstractLockController(Controller):
    def __init__(self, args):
        super().__init__(args)
        self.start_locked = args.locked

    @classmethod
    def augment_parser(cls, parser):
        parser.add_argument("--start-locked", action='store_true',
                            dest='locked', default=True,
                            help="Start in locked state (default)")
        parser.add_argument("--start-unlocked", action='store_false',
                            dest='locked',
                            help="Start in unlocked state")

    def initialize(self):
        self.log.debug("initialize: locked=%s", self.start_locked)

        if self.start_locked:
            self.enable_lock()
        else:
            self.disable_lock()

    @handler("/lock", int)
    async def received(self, lock: int):
        self.log.debug("received: lock=%d", lock)

        if lock:
            self.enable_lock()
        else:
            self.disable_lock()

    @handler("/lock/state")
    async def received_state(self):
        self.log.debug("received state query, return: %r", self.is_locked())
        return Response(1 if self.is_locked() else 0)

    @abc.abstractmethod
    def enable_lock(self):
        ...

    @abc.abstractmethod
    def disable_lock(self):
        ...

    @abc.abstractmethod
    def is_locked(self):
        ...


class LockController(AbstractLockController):
    @classmethod
    def augment_parser(cls, parser):
        super().augment_parser(parser)
        parser.add_argument("--pin", type=int, default=0,
                            help="Which WiringPi pin to use (default: 0)")
        parser.add_argument("--active-high", action='store_true',
                            dest='active_high', default=False,
                            help="Pin high is locked")
        parser.add_argument("--active-low", action='store_false',
                            dest='active_high',
                            help="Pin low is locked (default)")

    def __init__(self, args):
        super().__init__(args)
        self.pin = args.pin
        self.signal_locked = 1 if args.active_high else 0
        self.signal_unlocked = 0 if args.active_high else 1
        self.current_signal = self.signal_unlocked  # ???

    def initialize(self):
        if wiringpi is None:
            self.log.critical("WiringPi is not installed on this computer. "
                              "Please install it (pip3 install wiringpi)")
            sys.exit(1)

        wiringpi.wiringPiSetup()
        wiringpi.pinMode(self.pin, 1)

        super().initialize()

    def enable_lock(self):
        self.log.info("Enabling lock: setting pin %s to %s",
                      self.pin, "HIGH" if self.signal_locked else "LOW")
        self.current_signal = self.signal_locked
        wiringpi.digitalWrite(self.pin, self.signal_locked)

    def disable_lock(self):
        self.log.info("Disabling lock: setting pin %s to %s",
                      self.pin, "HIGH" if self.signal_unlocked else "LOW")
        self.current_signal = self.signal_unlocked
        wiringpi.digitalWrite(self.pin, self.signal_unlocked)

    def is_locked(self):
        return self.current_signal == self.signal_locked


class MockLockController(AbstractLockController):
    @classmethod
    def augment_parser(cls, parser):
        super().augment_parser(parser)
        parser.add_argument("--small-lock", action='store_true', default=False,
                            help="Use small lock text (default: big)")

    def __init__(self, args):
        super().__init__(args)
        self.big_lock = not args.small_lock
        self.current_state = None

    def enable_lock(self):
        if self.current_state is True:
            return

        if self.big_lock:
            print("""\
      ██████                                           .-. .-')     ('-.  _ .-') _
    ██      ██                                         \\  ( OO )  _(  OO)( (  OO) )
    ██      ██        ,--.      .-'),-----.    .-----. ,--. ,--. (,------.\\     .'_
  ██████████████      |  |.-') ( OO'  .-.  '  '  .--./ |  .'   /  |  .---',`'--..._)
██              ██    |  | OO )/   |  | |  |  |  |('-. |      /,  |  |    |  |  \\  '
██      ██      ██    |  |`-' |\\_) |  |\\|  | /_) |OO  )|     ' _)(|  '--. |  |   ' |
██      ██      ██   (|  '---.'  \\ |  | |  | ||  |`-'| |  .   \\   |  .--' |  |   / :
██              ██    |      |    `'  '-'  '(_'  '--'\\ |  |\\   \\  |  `---.|  '--'  /
  ██████████████      `------'      `-----'    `-----' `--' '--'  `------'`-------'""")
        else:
            print("\U0001F512 Mock lock: LOCKED")

        self.current_state = True

    def disable_lock(self):
        if self.current_state is False:
            return

        if self.big_lock:
            print("""\
      ██████
    ██      ██                     (               )        (
    ██      ██          (          )\\           ( /(    (   )\\ )
    ██                 ))\\   (    ((_) (    (   )\\())  ))\\ (()/(
  ██████████████      /((_)  )\\ )  _   )\\   )\\ ((_)\\  /((_) ((_))
██              ██   (_))(  _(_/( | | ((_) ((_)| |(_)(_))   _| |
██      ██      ██   | || || ' \\))| |/ _ \\/ _| | / / / -_)/ _` |
██      ██      ██    \\_,_||_||_| |_|\\___/\\__| |_\\_\\ \\___|\\__,_|
██              ██
  ██████████████""")
        else:
            print("\U0001F513 Mock lock: UNLOCKED")

        self.current_state = False

    def is_locked(self):
        return self.current_state
