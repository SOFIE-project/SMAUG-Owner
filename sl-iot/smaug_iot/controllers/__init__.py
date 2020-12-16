# entry points for different controllers
from .lock import LockController, MockLockController
from .wot import WotController
from .access import AccessController, MockAccessController
from .main import Main as _Main
from .nfc import NfcController
from .beacon import BeaconController
from .abstract import MultiController

lock = _Main("lock-controller", LockController, MockLockController)
wot = _Main("w3c-wot-controller", WotController)
access = _Main("access", AccessController, MockAccessController)
nfc = _Main("nfc", NfcController)
beacon = _Main("beacon", BeaconController)
mega_mock = _Main("mega-mock", MultiController(MockLockController,
                                               WotController,
                                               MockAccessController))
# this one includes all that have real version
mega = _Main(
    "mega",
    MultiController(LockController,
                    WotController,
                    AccessController,
                    NfcController,
                    BeaconController))
