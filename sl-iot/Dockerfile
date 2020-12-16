FROM alpine:3.12
# libusb is not used, but we'll get OSError during startup if it is not
# installed
RUN apk add --no-cache build-base python3 python3-dev py3-pip git mosquitto libusb
WORKDIR /smaug
COPY setup.py MANIFEST.in ./
COPY smaug_iot smaug_iot
RUN pip install .
COPY run-mock-smaug-iot.sh .
ENTRYPOINT ["./run-mock-smaug-iot.sh"]
EXPOSE 5000
CMD []
