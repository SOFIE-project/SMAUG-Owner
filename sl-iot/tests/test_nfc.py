import smaug_iot.nfc.messages as sm
import ndef
import pytest


def ktypes(*cls_list):
    return {"known_types": {cls._type: cls for cls in cls_list}}


def test_nfc_announce():
    record = sm.AnnounceRecord("id", "addr")
    packed = record._encode_payload()
    print(packed)

    # this is what should come out of msgpack
    assert packed == b'\x82\xb0contract_address\xa4addr\xa9locker_id\xa2id'

    octets = b''.join(ndef.message_encoder([record]))
    print(octets)

    decoded = list(
        ndef.message_decoder(octets, **ktypes(sm.AnnounceRecord)))
    print(decoded)

    assert len(decoded) == 1
    assert decoded[0].contract_address == "addr"
    assert decoded[0].locker_id == "id"


@pytest.mark.parametrize(
    "cls,fields,expected_packed,ndef_octets",
    [
        (sm.AnnounceRecord,
         {"contract_address": "addr", "locker_id": "id"},
         b'\x82\xb0contract_address\xa4addr\xa9locker_id\xa2id',
         (b'\xd4\x1b$smaug.sofie-iot.eu:announce\x82\xb0contract_address'
          b'\xa4addr\xa9locker_id\xa2id')),
        (sm.RequestRecord,
         {"action": "lock",
          "token": "sometoken"},
         b'\x82\xa5token\xa9sometoken\xa6action\xa4lock',
         (b'\xd4\x1a\x1dsmaug.sofie-iot.eu:request\x82\xa5token\xa9'
          b'sometoken\xa6action\xa4lock')),
        (sm.RejectedRecord,
         {},
         b'',
         b'\xd4\x1b\x00smaug.sofie-iot.eu:rejected'),
        (sm.AcceptedRecord,
         {"state": "locked"},
         b'\x81\xa5state\xa6locked',
         b'\xd4\x1b\x0esmaug.sofie-iot.eu:accepted\x81\xa5state\xa6locked'),
    ])
def test_nfc_roundtrip(cls, fields, expected_packed, ndef_octets):
    record = cls(**fields)
    packed = record._encode_payload()
    print(cls, fields, packed)
    assert packed == expected_packed

    octets = b''.join(ndef.message_encoder([record]))
    print(octets)

    assert ndef_octets == octets

    decoded = list(ndef.message_decoder(octets, **ktypes(cls)))
    print(decoded)

    assert len(decoded) == 1
    assert isinstance(decoded[0], cls)
    for k, v in fields.items():
        print(k, getattr(decoded[0], k), "<->", v)
        assert getattr(decoded[0], k) == v
