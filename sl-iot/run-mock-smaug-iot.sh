#!/bin/sh -e
mosquitto -d
exec mega-mock-controller "$@"
