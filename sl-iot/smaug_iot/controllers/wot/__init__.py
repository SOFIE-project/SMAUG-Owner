import abc
import asyncio
import uuid
from ..abstract import Controller, handler
from ..main import parse_host
from ..lock import LockController
from ..access import AccessSchema
from quart import Quart, Blueprint, jsonify, current_app, request
from quart import abort, render_template

root = Blueprint('root', __name__, url_prefix='/')


def get_token():
    if 'Authorization' not in request.headers:
        return None

    try:
        auth_type, auth_info = request.headers['Authorization'].split(None, 1)
    except ValueError:
        return None

    if auth_type.lower() != 'bearer':
        return None

    return auth_info


# maybe make this a decorator later
async def check_access(*actions):
    token = get_token()

    if not token:
        abort(401)

    ok, allowed = await current_app.controller.check_access(token, *actions)

    if not ok:
        abort(503)

    if not allowed:
        abort(403)


@root.route("/")
async def index():
    return await render_template("index.html")


@root.route("/api/status")
async def status():
    await check_access("state")
    return current_app.controller.locked_str


@root.route("/api/status/locked")
async def locked():
    await check_access("state")
    return current_app.controller.locked_num


@root.route("/api/action/lock", methods=["POST", "PUT"])
async def lock():
    await check_access("lock")
    current_app.controller.lock_action()
    return "locked"


@root.route("/api/action/unlock", methods=["POST", "PUT"])
async def unlock():
    await check_access("unlock")
    current_app.controller.unlock_action()
    return "unlocked"


class WotController(Controller):
    def __init__(self, args):
        super().__init__(args)
        self.address = args.address

        self.locked_str = "unknown"
        self.locked_num = "null"

        self.app = Quart(__name__)
        self.app.controller = self
        self.app.register_blueprint(root)
        self.app.config['TEMPLATES_AUTO_RELOAD'] = True

    @classmethod
    def augment_parser(cls, parser):
        parser.add_argument(
            '--bind', '-a',
            type=parse_host,
            dest='address',
            default=parse_host("0.0.0.0:5000"),
            help="Address to bind to (default 0.0.0.0:5000)")

    def initialize(self):
        self.task = asyncio.create_task(
            self.app.run_task(*self.address, debug=False))

        self.log.debug("started %r on %r", self.task, self.address)

    # this needs later to be refactored into more generic approach,
    # this is not a bit of a kludge
    reqs = {}

    @handler("/access_result", AccessSchema())
    async def check_result(self, id, allowed, **kwargs):
        if id not in self.reqs:
            self.log.debug("access result for %r received, not in reqs", id)
            return

        event = self.reqs[id][0]
        self.reqs[id] = event, True, allowed
        event.set()

    async def check_access(self, token, *actions):
        id = str(uuid.uuid4())

        self.log.debug("check_access: token=%r actions=%r id=%r",
                       token, actions, id)

        event = asyncio.Event()
        self.reqs[id] = event, False, False

        self.publish("/access",
                     AccessSchema().dumps({
                         "id": id,
                         "token": token,
                         "actions": actions}),
                     response_topic="/access_result")

        self.log.debug("published, wait event %r", event)

        try:
            await asyncio.wait_for(event.wait(), 60)
            result = self.reqs[id][1:]
        except asyncio.TimeoutError:
            result = False, False

        del self.reqs[id]

        self.log.debug("id=%r result: %r", id, result)

        return result

    @handler("/lock", int)
    async def lock_message(self, locked):
        self.log.debug("lock message, locked=%r", locked)

        if locked == 0:
            self.locked_str = "unlocked"
            self.locked_num = "0"
        else:
            self.locked_str = "locked"
            self.locked_num = "1"

    def lock_action(self):
        self.log.debug("lock_action called")
        self.publish("/lock", "1")

    def unlock_action(self):
        self.log.debug("unlock_action called")
        self.publish("/lock", "0")
