# import paho.mqtt.client as mqtt
from gmqtt import Client as MQTTClient, Subscription
import asyncio
import sys
import signal
import json
import logging
from marshmallow import Schema, fields, post_load
import argparse


def parse_host(s):
    if ':' in s:
        h, a = s.split(':')
        return h, int(a)

    return s, 1883


class Main(object):
    """Generic main handler taking in real controller and an optional mock
    controller class. The main handler (this one) handles generic common
    parameters related to SMAUG components such as MQTT client
    management.

    The controllers are expected to provide a list of addresses and
    handlers they want to subscribe to.

    """
    def __init__(self, name, real_cls, mock_cls=None, description=""):
        self.name = name
        self.description = description
        self.real_cls = real_cls
        self.mock_cls = mock_cls
        self.log = logging.getLogger(name)
        self.stop = asyncio.Event()

    def get_parser(self):
        parser = argparse.ArgumentParser(self.name,
                                         self.description,
                                         add_help=False)

        # add common arguments
        parser.add_argument(
            '--mqtt-server', '--server', '-s',
            type=parse_host,
            dest='server',
            default=parse_host("localhost:1883"),
            help="Address of the MQTT server (default: localhost:1883)")
        parser.add_argument(
            '--mqtt-client-id', dest='client_id',
            default=self.name,
            help=f"MQTT client id (default {self.name})")
        if self.mock_cls is not None:
            parser.add_argument(
                '--mock', '--use-mock', action='store_true',
                dest='use_mock', help="Use a mock implementation")
            parser.add_argument(
                '--real', '--use-real', action='store_false',
                dest='use_mock', help="Use the real implementation (default)")
        parser.add_argument(
            '--prefix', '-p', type=str, default='',
            help="Subscription address prefix (default: '')")
        parser.add_argument(
            '--inject-message', '-i', default=[], action='append', type=str,
            help="Inject messages to the client")
        parser.add_argument(
            '--once', dest='run_once', default=False, action='store_true',
            help="Run only once, e.g. process incoming messages and then exit")
        parser.add_argument('-d', '--debug',
                            action='store_const', dest='debug_level',
                            default={
                                "": logging.INFO,
                                "gmqtt": logging.WARN,
                                "quart.serving": logging.WARN},
                            const={
                                "": logging.DEBUG
                            },
                            help="Produce debug output")
        parser.add_argument('-q', '--quiet',
                            action='store_const', dest='debug_level',
                            const={
                                "": logging.ERROR,
                                "quart.serving": logging.WARN
                            },
                            help="Be quiet and output only errors")
        parser.add_argument('-h', '--help', action='store_true',
                            help='Show help')

        # mock option might not be defined at all, so specify the
        # default (real controller) explicitly
        parser.set_defaults(use_mock=False)

        return parser

    def __call__(self):
        loop = asyncio.get_event_loop()

        def stop():
            print("^C detected, stopping...")
            self.stop.set()

        loop.add_signal_handler(signal.SIGINT, stop)
        loop.add_signal_handler(signal.SIGTERM, stop)

        try:
            loop.run_until_complete(self.main())
        except KeyboardInterrupt:
            self.log.info("Exiting...")

    def publish(self, topic, data=None, **kwargs):
        self.log.debug("publishing: topic=%r data=%r kwargs=%r",
                       topic, data, kwargs)
        self.client.publish(topic, data, **kwargs)

    def subscribe(self):
        for topic, (fns, sub, subid) in self.subscriptions.items():
            if sub is not None:
                self.client.resubscribe(sub)
                continue

            sub = Subscription(self.prefix + topic)

            self.subscriptions[topic] = (fns, sub, subid)
            self.client.subscribe(sub, subscription_identifier=subid)

            self.log.debug("subscribed: topic=%r sub=%r subid=%r mid=%r",
                           topic, sub, subid, sub.mid)

    def on_connect(self, *args, **kwargs):
        self.log.debug(f"on_connect: self=%r args=%r kwargs=%r",
                       self, args, kwargs)
        self.subscribe()

    async def on_message(self, client, topic, payload, qos, properties):
        self.log.debug("on_message: client=%r topic=%r payload=%r "
                       "qos=%r properties=%r",
                       client, topic, payload, qos, properties)

        # look for matching handler and call it
        for subid in properties['subscription_identifier']:
            for topic, (fns, sub, subid2) in self.subscriptions.items():
                if subid == subid2:
                    self.log.debug("subid=%r match, fns=%r", subid, fns)
                    await asyncio.wait([fn(payload, properties) for fn in fns])

        return 0

    async def main(self):
        # Parse args twice, first with the default parser, then with
        # the augmented parser once we know whether we use real or
        # mock controller.
        parser = self.get_parser()
        args, unknown = parser.parse_known_args()
        logging.basicConfig()

        for logger, level in args.debug_level.items():
            logging.getLogger(logger).setLevel(level)

        controller_cls = self.mock_cls if args.use_mock else self.real_cls
        controller_cls.augment_parser(parser)
        args = parser.parse_args()

        if args.help:
            parser.print_help()
            sys.exit(0)

        self.prefix = args.prefix

        # Create controller---it has now a chance to fail on invalid
        # arguments etc., but actual initialization occurs only once
        # we have an established connection.
        self.controller = controller_cls(args)

        self.log.debug("controller_cls=%r controller=%r args=%r",
                       controller_cls, self.controller, args)

        self.client = MQTTClient(args.client_id)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        # subscriptions: key = topic, value = ([fns], sub, sid)
        self.subscriptions = {}

        for topic, fn in self.controller.subscriptions:
            self.subscriptions.setdefault(
                topic, ([], None, len(self.subscriptions) + 1))[0].append(fn)

        self.log.debug("subscriptions=%r", self.subscriptions)

        # hook up the publisher before initialize, it might be called there
        self.controller.set_publisher(self.publish)

        # # initialize the client now
        # self.controller.initialize()

        while not (self.stop.is_set() or self.client.is_connected):
            try:
                await self.client.connect(*args.server, keepalive=60)
            except OSError:
                self.log.warning(
                    "Warning: Unable to connect to %s:%d, retrying...",
                    *args.server)

                # wait either until stop is set, or for the reconnect
                # timeout
                try:
                    await asyncio.wait_for(self.stop.wait(), 30)
                except asyncio.TimeoutError:
                    pass

        if not self.client.is_connected:
            return

        try:
            self.log.info("Note: Connected to %s:%d", *args.server)
            self.controller.initialize()

            for message in args.inject_message:
                assert False, "NOT IMPLEMENTED"

                # # not clean re-use of Namespace thought...
                # self.handle_message(controller, argparse.Namespace(
                #     payload=message.encode('utf-8')))

            if args.run_once:
                self.stop.set()

            self.log.debug("waiting for stop signal")
            await self.stop.wait()
            self.log.debug("stopped")
        except KeyboadInterrupt:
            self.log.info("^C detected, stopping...")
        except:
            self.log.exception("exception during controller operation")
        finally:
            self.log.debug("uninitializing controller")
            self.controller.uninitialize()

            self.log.debug("disconnecting")
            await self.client.disconnect()
