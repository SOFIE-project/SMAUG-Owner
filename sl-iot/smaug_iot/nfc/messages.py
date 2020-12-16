from abc import ABC
import msgpack


class DecodeError(Exception):
    pass


class Message(ABC):
    FIELDS = ()
    _TYPES = []

    def __init_subclass__(cls, *args, **kwargs):
        # print("__init_subclass__:", cls, args, kwargs)
        Message._TYPES.append(cls)
        return super().__init_subclass__(*args, **kwargs)

    def __init__(self, *args, **kwargs):
        super().__setattr__('_values', {})

        if len(args) > len(self.FIELDS):
            raise DecodeError(f"More initializer values than fields: "
                              f"{args!r} vs {self.FIELDS!r}")

        for i, value in enumerate(args):
            self._values[self.FIELDS[i]] = value

        for field, value in kwargs.items():
            if field in self._values:
                raise DecodeError(
                    f"Field {field!r} already defined by array arguments")

            if field not in self.FIELDS:
                raise DecodeError(
                    f"Field {field!r} is not defined for this record type")

            self._values[field] = value

        if len(self._values.keys()) != len(self.FIELDS):
            raise DecodeError(f"Not all fields were initialized, missing: "
                              f"{set(self.FIELDS) - set(self._values.keys())}")

    def __getattr__(self, field):
        if field not in self._values:
            raise DecodeError(f"{field} not recognized")
        return self._values[field]

    def __setattr__(self, field, value):
        assert False, (field, value)

    def __str__(self):
        return (self.__class__.__name__
                + "{"
                + ','.join(f"{k}={v!r}" for k, v in self._values.items())
                + "}")

    __repr__ = __str__

    def encode(self):
        return bytes([self.TYPE]) + msgpack.packb(self._values)

    @classmethod
    def decode(cls, data):
        if len(data) < 1:
            raise DecodeError("No message to decode")

        type_value = int(data[0])

        for cls in Message._TYPES:
            # print(type_value, cls, cls.TYPE)
            if cls.TYPE == type_value:
                unpacked = msgpack.unpackb(data[1:])
                return cls(**unpacked)

        # # # print(Message._TYPES, type_value, data[1:].hex())
        # # # super kludge to work around things in moshipack in the
        # # # client I do not have time to fix
        # # if 'type' in unpacked:
        # #     del unpacked['type']

        # # print("unpacked:", unpacked)
        # for cls in Message._TYPES:
        #     # print(type_value, cls, cls.TYPE)
        #     if cls.TYPE == type_value:
        #         return cls(**unpacked)

        raise DecodeError(f"Type {hex(type_value)} not a known record type")


class Announce(Message):
    TYPE = 0b10_000_000
    FIELDS = ("contract_address", "locker_id", "name", "image_urls",
              "open_close_type")


class Verify(Message):
    TYPE = 0b00_000_001
    FIELDS = ("token",)


class VerifySuccess(Message):
    TYPE = 0b10_000_001
    FIELDS = tuple()


class VerifyFailure(Message):
    TYPE = 0b11_000_001
    FIELDS = ("message",)


class Echo(Message):
    TYPE = 0b00_100_000
    FIELDS = ("message",)


class EchoSuccess(Message):
    TYPE = 0b10_100_000
    FIELDS = ("message",)


class Query(Message):
    TYPE = 0b00_000_010
    FIELDS = tuple()


class QuerySuccess(Message):
    TYPE = 0b10_000_010
    FIELDS = ("state",)


class QueryFailure(Message):
    TYPE = 0b11_000_010
    FIELDS = ("message",)


class Open(Message):
    TYPE = 0b00_000_011
    FIELDS = tuple()


class OpenSuccess(Message):
    TYPE = 0b10_000_011
    FIELDS = ("state",)


class OpenFailure(Message):
    TYPE = 0b11_000_011
    FIELDS = ("message", "state")


class Close(Message):
    TYPE = 0b00_000_100
    FIELDS = tuple()


class CloseSuccess(Message):
    TYPE = 0b10_000_100
    FIELDS = ("state",)


class CloseFailure(Message):
    TYPE = 0b11_000_100
    FIELDS = ("message", "state")
