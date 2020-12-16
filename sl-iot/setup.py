#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name='smaug-iot',
    version='0.1.0',
    packages=find_packages(exclude=['tests']),
    python_requires='>=3.7',
    install_requires=[
        'gmqtt',
        'marshmallow',
        'Quart',
        'iso8601',
        'pytz',
        'aiohttp',
        'msgpack',
        'nfcpy',
        ('sofie_pd_component@git+'
         'https://github.com/SOFIE-project'
         '/Discovery-and-Provisioning.git'
         '#egg=sofie_pd_component')
    ],
    extras_require={
        'dev': [
            'pytest',
            'sphinx',
            'jsonschema',
            ]
    },
    entry_points={
        'console_scripts': [
            'lock-controller=smaug_iot.controllers:lock',
            'wot-controller=smaug_iot.controllers:wot',
            'access-controller=smaug_iot.controllers:access',
            'nfc-controller=smaug_iot.controllers:nfc',
            'mega-mock-controller=smaug_iot.controllers:mega_mock',
            'mega-controller=smaug_iot.controllers:mega',
            "beacon-controller=smaug_iot.controllers:beacon",
        ],
    },
    tests_require=['pytest', 'pytest-asyncio', 'jsonschema'],
    include_package_data=True
)
