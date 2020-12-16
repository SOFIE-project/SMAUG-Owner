import abc
import iso8601
import pytz
import aiohttp
from urllib.parse import urljoin
from aiohttp.client_exceptions import \
    ClientResponseError, ClientConnectionError
from .abstract import Controller, handler, Response
from marshmallow import Schema, fields
from datetime import datetime, timedelta


class AccessSchema(Schema):
    id = fields.String(missing=None)
    token = fields.String(required=True)
    valid = fields.Boolean()
    allowed = fields.Boolean(missing=False)
    actions = fields.List(fields.String, missing=["lock", "unlock", "state"])
    expires = fields.DateTime(allow_none=True)


all_actions = ("lock", "unlock", "state")


class AbstractAccessController(Controller):
    @abc.abstractmethod
    async def check_token(self, token):
        """Check the given token and return a tuple of (valid,
        allowed_actions, expires)"""
        ...

    @handler("/access", AccessSchema())
    async def access_message(self, id, token, actions, **kwargs):
        valid, allowed_actions, expires = await self.check_token(token)

        allowed = (valid
                   and set(actions) <= set(allowed_actions)
                   and expires >= datetime.now(tz=pytz.utc))

        print(f"{'ALLOWED' if allowed else 'DENIED'}: "
              f"{token} -- {id} "
              f"-- {','.join(allowed_actions)}")

        return Response({"id": id,
                         "token": token,
                         "valid": valid,
                         "allowed": allowed,
                         "actions": allowed_actions,
                         "expires": expires})


class MockAccessController(AbstractAccessController):
    """The mock access controller will try to parse the token with the
    format of

        0/1;action,action,...;expires(iso8601)

    For convenience, if the action string is "all" then a permissive
    set of actions is included. Also remember that a pure YEAR is a
    valid ISO8601 string, e.g. "9999" == "9999-01-01T01:01:01+0000",
    thus passing "1;all;9999" is a short permissive version.

    If parsing fails, this will return essentially "valid", "all
    allowed" and "expires tomorrow" response. So if you just want to
    get this to pass, you can pass an arbitrary value instead.

    """

    async def check_token(self, token):
        self.log.debug("check_token: token=%r", token)

        try:
            valid, allowed, expires = token.split(";")

            valid = bool(int(valid))
            allowed = all_actions if allowed == "all" else allowed.split(",")
            expires = iso8601.parse_date(expires)
        except (ValueError, iso8601.iso8601.ParseError) as ex:
            self.log.warn("check_token: unparseable token, "
                          "using defaults, error: %s",
                          ex)

            valid = True
            allowed = all_actions
            expires = datetime.now(tz=pytz.utc) + timedelta(days=1)
        finally:
            pass

        self.log.debug("check_token: valid=%r allowed=%r expires=%r",
                       valid, allowed, expires)

        return (valid, allowed, expires)


class AccessController(AbstractAccessController):
    """This uses the IAA validation component to validate the token"""

    @classmethod
    def augment_parser(cls, parser):
        parser.add_argument(
            "--iaa-server",
            default="http://localhost:9000/secure/jwt-noproxy",
            help=("IAA server address (default: "
                  "http://localhost:9000/secure/jwt-noproxy"))

    def __init__(self, args):
        super().__init__(args)
        self.url = args.iaa_server
        self.session = aiohttp.ClientSession()

    async def check_token(self, token):
        self.log.debug("check_token: token=%r url=%r",
                       token, self.url)

        # url = urljoin(self.url, "verifytoken")
        url = self.url
        data = {
            # "token-type": "Bearer",
            # "token": token
        }
        headers = {
            "Authorization": "Bearer " + token
        }

        try:
            self.log.debug("check_token: querying URL %s, data %r, headers %r",
                           url, data, headers)

            async with self.session.get(
                    url, data=data, headers=headers) as response:
                self.log.debug("check_token: response: %s", response)

                if response.status == 200:
                    # not really interested in the payload actually,
                    # currently id does not have expiry header or
                    # anything other useful
                    # result = await response.json(content_type=None)

                    # just allow all now
                    return (
                        True,
                        all_actions,
                        datetime.now(tz=pytz.utc) + timedelta(hours=1))
        except (ClientResponseError, ClientConnectionError):
            self.log.exception("Error from server")

        # default is just to deny otherwise
        return (False, (), None)
