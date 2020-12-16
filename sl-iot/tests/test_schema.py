import jsonschema
import json


def test_locker_schema():
    schema = json.loads(open("td-json-schema-validation.json").read())
    locker = json.loads(open("thing-description/locker.json").read())
    jsonschema.validate(instance=locker, schema=schema)
