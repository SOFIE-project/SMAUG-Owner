from .abstract import Controller
import sofie_pd_component.eddystone_uuid as eddystone_uuid


class BeaconController(Controller):
    def __init__(self, args):
        super().__init__(args)
        self.iid = bytes.fromhex(args.locker_iid[:12]).rjust(6, b'\x00')
        self.nsid = bytes.fromhex(args.locker_nsid[:20]).rjust(10, b'\x00')
        self.hci = args.hci

    @classmethod
    def augment_parser(cls, parser):
        parser.add_argument(
            '--locker-iid',
            type=str, metavar='IID',
            default="000102030405",
            help=("Eddystone UID instance identifier (6 bytes, in hex, "
                  "left-padded with zeros if shorter, default "
                  "is 000102030405)"))
        parser.add_argument(
            '--locker-nsid',
            type=str, metavar='NSID',
            # this is just from 10 bytes from /dev/random
            default="b8c7153ef9389a7cd65d",
            help=("Eddystone UID namespace identifier (10 bytes, in hex, "
                  "left-padded with zeros if shorter, default "
                  "is SMAUG NSID b8c7153ef9389a7cd65d)"))
        parser.add_argument('--hci',
                            default='hci0',
                            help="The bluetooth HCI device (default hci0)")

    def initialize(self):
        self.log.debug("Setting up %s for nsid %s iid %s",
                       self.hci, self.nsid, self.iid)
        eddystone_uuid.startUuidAdvertise(INTERFACE=self.hci,
                                          NAMESPACE=self.nsid,
                                          INSTANCEID=self.iid)

    def uninitialize(self):
        self.log.debug("Disabling HCI device %s", self.hci)
        eddystone_uuid.stopUuidAdvertise()
