import abc
import logging
import json
import marshmallow
import functools


class Response(object):
    def __init__(self, data):
        self.data = data


def handler(topic, schema=None, response_schema=None):
    response_schema = response_schema or schema

    def wrap(fn):
        @functools.wraps(fn)
        async def call(self, payload, properties):
            raw_data = json.loads(payload.decode()) if len(payload) else None

            logging.debug("handle_message: topic=%r schema=%r fn=%r "
                          "raw_data=%r",
                          topic, schema, fn, raw_data)

            try:
                if schema is None:
                    data = raw_data
                elif isinstance(schema, marshmallow.Schema):
                    data = schema.load(raw_data)
                else:
                    data = schema(raw_data)
            except marshmallow.exceptions.ValidationError as ex:
                logging.warn("Received validation error, "
                             "dropping request: %s", ex)
                return

            logging.debug("schema=%r data=%r fn=%r", schema, data, fn)

            if isinstance(data, dict):
                result = await fn(self, **data)
            elif isinstance(data, (list, tuple)):
                result = await fn(self, *data)
            elif len(payload):
                result = await fn(self, data)
            else:
                result = await fn(self)

            if isinstance(result, Response):
                if 'response_topic' not in properties:
                    logging.warn("Response without response topic, "
                                 "response silently dropped")
                else:
                    if response_schema:
                        raw_result = response_schema.dumps(
                            result.data).encode('utf-8')
                    else:
                        raw_result = json.dumps(result.data)

                    logging.debug("result=%r raw_result=%r",
                                  result, raw_result)

                    self.publish(properties['response_topic'][0], raw_result)

        call.topic = topic

        return call
    return wrap


class Controller(abc.ABC):
    """Abstract class that represents a controller that will only receive
    commands via the message bus.

    This interacts with main runner by:

    __init__(self, args) -- normally as constructor, this should not
    "start" anything, passed parsed command-line arguments

    @classmethod augment_parser -- can be used to add new parameters
    to command line parsing (this is a classmethod)

    set_publisher(publisher) -- called to set a callback to publish
    messages

    initialize(self) -- called with parsed
    command-line arguments, this may start things (connect to pins,
    set them to defaults etc.)

    uninitialize(self) -- the controller should prepare for removal,
    e.g. disable processes etc.

    subscriptions -- a list of (topic, handler)

    """

    def __init__(self, args):
        self.log = logging.getLogger(self.__class__.__name__)
        self._publish = None

        subscriptions = set()

        for name in dir(self):
            if name == 'subscriptions':
                continue

            method = getattr(self, name)

            if isinstance(method, property):
                method = method.fget

            if hasattr(method, 'topic'):
                subscriptions.add((method.topic, method))

        self._subscriptions = list(subscriptions)

    @classmethod
    def augment_parser(cls, parser):
        pass

    def initialize(self):
        pass

    def uninitialize(self):
        pass

    def set_publisher(self, publisher):
        self._publisher = publisher

    def publish(self, *args, **kwargs):
        self._publisher(*args, **kwargs)

    @property
    def subscriptions(self):
        return self._subscriptions


class MultiController(object):
    """This is a controller generator that will provide an interface to
    multiple different controllers. The intention is to provide a
    single script that integrates multiple controllers (for
    performance and memory usage reasons).

    """

    class MultiControllerImpl(object):
        def __init__(self, args, controllers):
            self.log = logging.getLogger(self.__class__.__name__)
            self.controllers = controllers
            self.subscriptions = []

            for c in self.controllers:
                self.subscriptions.extend(c.subscriptions)

            self.log.debug("__init__: controllers=%r subscriptions=%r",
                           self.controllers, self.subscriptions)

        def set_publisher(self, publisher):
            for c in self.controllers:
                c.set_publisher(publisher)

        def initialize(self):
            for c in self.controllers:
                c.initialize()

        def uninitialize(self):
            for c in self.controllers:
                c.uninitialize()

    # This is constructor to create a stand-in for the metaclass
    def __init__(self, *classes):
        self.log = logging.getLogger(self.__class__.__name__)
        self.classes = classes

    # This is what looks like the constructor to caller
    def __call__(self, args):
        self.log.debug("args=%r", args)
        impl = MultiController.MultiControllerImpl(
            args,
            [cls(args) for cls in self.classes])
        self.log.debug("impl=%r", impl)
        return impl

    def augment_parser(self, parser):
        for cls in self.classes:
            cls.augment_parser(parser)
