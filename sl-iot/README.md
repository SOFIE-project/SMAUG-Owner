# SMAUG IoT Platform

## Quickstart

This section is for quick start instructions to get the development
environment working and running, for more detailed information on how
to run the controllers see further below.

### Developer Setup

(Optional) Setup python virtualenv (the platform software requires
Python 3.7 or later), for example by:

    $ pyenv virtualenv 3.7.5 smaug-iot
	$ pyenv activate smaug-iot

Then setup the environment for development (pip install is needed
to get the controller scripts into executable path, if you don't need
those you can use `python setup.py develop` instead):

	$ pip install --editable '.[dev]'

Now you can try either the mock or real version of the lock
controller, for example:

	$ lock-controller --mock
	$ lock-controller --real

Since these assume you have a MQTT broker at localhost, you might want
to install Mosquitto or other MQTT broker and start it. For example
using the `mosquitto-local.conf` to bind only to `127.0.0.1` address
(localhost):

	$ mosquitto -v -c mosquitto-local.conf

Then you can try to control the lock directly:

    $ mosquitto_pub -t /lock -m 1
    $ mosquitto_pub -t /lock -m 0

You can also run all of the system in a single controller:

    $ mega-mock-controller

This has WoT HTTP server enabled with a simple single-page application
using the API at [http://localhost:5000](port 5000).

### Hardware setup

**YOU MUST HAVE PYTHON 3.7 INSTALLED!** While Raspbian (at least at
the time of writing) installs 3.6 by default, a 3.7 version is
available:

    $ sudo apt install python3.7

**YOU MUST HAVE A MQTTv5 SUPPORTING VERSION OF MOSQUITTO INSTALLED!**
Again, Raspbian default (at this time) is an older version. See if you
have at least 1.6.8 (known to
work). [https://raspberrypi.stackexchange.com/a/80101](Here are some
instructions), but keep in mind that at least a recent version of
Raspbian is named `buster`.

If you are running any of the controllers on actual Raspberry Pis you
will need some additional libraries installed:

    $ sudo pip3 install wiringpi nfcpy

## Documentation

To generate the HTML documentation, run:

    make doc

You will find the documentation then in
[doc/_build/html/index.html](doc/_build/html/index.html).

## Running and testing

The IoT platform is comprised of separate **controllers**, defined in
`smaug_iot`. For development purposes these are often run and
configured separately. Each of the controller supports a few common
options such as for setting MQTT host (`--mqtt-server`,
`--mqtt-client-id`, `--mqtt-prefix`, `--once`, `--debug`, `--quiet`)
as well as selecting between the "real" controller (`--real`, this is
the default) or using potentially available mock controller
(`--mock`).

The individual controllers are:

`lock-controller`
: Managing the lock. The real controller requires WiringPi library
: and works only on a Raspberry Pi. The mock lock controller will just
: print out any changes in its state.

`wot-controller`
: Provides a REST interface for controlling the lock (W3C WoT
: compliant interface). There's no mock controller since this
: interfaces only via other controllers.

`access-controller`
: Provides access token verification and validation for other
  controllers (WoT and NFC, in particular).

There's also a few "mega" controllers which subsume all of the
required controller functionality into a single script, for ease of
deployment and performance reasons. Specifically:

`mega-mock-controller`
: This uses mock controllers for services where they are
: available. Essentially this mocks the whole system in a single
: program.

`mega-controller`
: This uses all available real controllers for services where they are
: available and mocks for others. You'll need the actual required
: Raspberry Pi hardware to run this.

## Dockerized mock IoT device

You can build a docker container that contains a all of the
controllers (`mega-mock-controller`). Normally in a Raspberry Pi you
wouldn't use docker to run the controller, so this is mostly just
useful for non-device testing and mock setups.

The container runs the `mega-mock-controller` directly (well, it
starts a mosquitto server internally first), so you can just pass it
directly whatever options apply to that, e.g.:

	$ docker build -t smaug-iot .
	$ docker run --rm -p 5000:5000 smaug-iot

There is a WoT controller accessible on port 5000, try navigating to
[http://localhost:5000](http://localhost:5000/).

Note: There's some funny going on with some of the controllers and ^C
signalling --- you need to use `docker stop` to terminate the
container.
