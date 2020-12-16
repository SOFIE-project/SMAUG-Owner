try:
    import nfc
    import nfc.clf
except ImportError:
    nfc = None

import logging
from .messages import Message, DecodeError


def ok(req, data):
    if isinstance(data, str):
        data = ba(data)
    return bytes([0x02 | req[0] & 0x01]) + data


class Proto(object):
    def __init__(self, clf, aid, timeout=0):
        self.clf = clf
        self.aid = aid
        self.timeout = timeout
        self.log = logging.getLogger(self.__class__.__name__)

    def _exchange(self, data):
        try:
            # we need to keep last result for ok bit set, but don't
            # use it otherwise
            self.result = self.clf.exchange(
                ok(self.result, data), self.timeout)
            return self.result
        except (nfc.clf.TransmissionError, OSError):
            return None

    def listen(self, timeout=None):
        # Repeatedly acquire new target and listen, return only
        # when we have the defined AID detected
        if nfc is None:
            logging.critical("nfcpy is not installed on this computer. "
                             "Please install it (pip3 install nfcpy)")
            sys.exit(1)

        timeout = self.timeout if timeout is None else timeout

        while True:
            target = nfc.clf.LocalTarget('106A')
            target.sens_res = b'\x01\x01'
            target.sdd_res = b'\x08\x01\x02\x03'
            target.sel_res = b'\x20'

            try:
                self.target = self.clf.listen(target, self.timeout)
            except OSError:
                self.target = None

            if not self.target:
                return False

            tt4_cmd = self.target.tt4_cmd
            self.result = tt4_cmd

            self.log.debug(f"CONNECTED: tt4_cmd: {tt4_cmd and tt4_cmd.hex()}")

            # Probe?
            if tt4_cmd == b'\x02\x00\xb0\x00\x00\x01':
                self._exchange(b'\x90\x00')
                self.log.info("PROBE: respond SUCCESS")
                continue

            if not tt4_cmd:
                self.log.info("No TT4 command, rejected")
                # probably should send a NAK response at this
                # point--contiuing will simply terminate the NFC
                # connection
                continue

            # print("HEADER:", tt4_cmd[1:6].hex())

            match = False

            if len(tt4_cmd) >= 4 and tt4_cmd[1:5] == b'\x00\xa4\x04\x00':
                lc = int(tt4_cmd[5])
                self.log.debug(f"SELECT DF LC={lc}")
                if len(tt4_cmd) < 1 + 4 + lc:
                    self.log.warning(f"DF name truncated, rejecting")
                    continue

                name = tt4_cmd[6:6 + lc]
                self.log.debug(f"SELECT DF NAME={name}")

                if name != self.aid:
                    self.log.warning(
                        f"NAME is not our AID ({self.aid}), rejecting")
                    continue

                match = True

            if not match:
                self.log.info("Incorrect protocol start, rejecting")
                continue

            self.log.info("SELECT DF: Expected AID detected")
            return True

    def send(self, data):
        reply = self._exchange(data)

        if reply is None:
            return None

        self.log.debug(f"sent {data.hex()}, received {reply.hex()}")

        # TODO: check result header
        if reply[0] == 0xb3:
            self.log.info("B3 response")
            return None

        return reply[1:]


class Nfc(object):
    def __init__(self, device,
                 aid="eu.sofie-iot.smaug.locker.1".encode('iso-8859-1'),
                 timeout=0):
        self.clf = nfc.ContactlessFrontend(device)
        self.proto = Proto(self.clf, aid, timeout)
        self.log = logging.getLogger(self.__class__.__name__)

    def listen(self):
        return self.proto.listen()

    def send(self, msg):
        encoded = msg.encode()
        self.log.debug(">>> %r = %r (%d bytes)", msg, encoded, len(encoded))

        data = bytearray()
        frame = self.proto.send(encoded)

        while True:
            if frame is None or len(frame) == 0:
                self.log.debug("<<< received null frame, dropping")
                return None

            # continuation frame in response?
            type = frame[0]

            if type & 0b00100000:
                self.log.debug("0x%02x CONT: %d bytes", type, len(frame) - 1)
                data = data + frame[1:]
                frame = self.proto.send(bytearray([type]))
                continue

            self.log.debug("0x%02x FIN:  %d bytes", type, len(frame) - 1)
            data = bytearray([type]) + data + frame[1:]

            self.log.debug("<<< %r (%d bytes)", data, len(data))

            try:
                msg = Message.decode(data)
                self.log.debug("<<< = %r", msg)
                return msg
            except DecodeError as err:
                self.log.debug("Error decoding message %r: %s", data, err)
                return None

    def close(self):
        self.clf.close()
