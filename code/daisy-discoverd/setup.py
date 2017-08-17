# Copyright 2012 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import re

from setuptools import setup


try:
    # Distributions have to delete *requirements.txt
    with open('requirements.txt', 'r') as fp:
        install_requires = [re.split(r'[<>=]', line)[0]
                            for line in fp if line.strip()]
except EnvironmentError:
    print("No requirements.txt, not handling dependencies")
    install_requires = []


with open('daisy_discoverd/__init__.py', 'rb') as fp:
    exec(fp.read())


setup(
    name = "daisy-discoverd",
    version = __version__,
    description = open('README.rst', 'r').readline().strip(),
    author = "Dmitry Tantsur",
    author_email = "dtantsur@redhat.com",
    url = "https://pypi.python.org/pypi/daisy-discoverd",
    packages = ['daisy_discoverd', 'daisy_discoverd.plugins',
                'daisy_discoverd.test'],
    install_requires = install_requires,
    entry_points = {
        'console_scripts': [
            "daisy-discoverd = daisy_discoverd.main:main"
        ],
        'daisy_discoverd.hooks': [
            "scheduler = daisy_discoverd.plugins.standard:SchedulerHook",
            "validate_interfaces = daisy_discoverd.plugins.standard:ValidateInterfacesHook",
            "ramdisk_error = daisy_discoverd.plugins.standard:RamdiskErrorHook",
            "example = daisy_discoverd.plugins.example:ExampleProcessingHook",
        ],
    },
    classifiers = [
        'Development Status :: 5 - Production/Stable',
        'Environment :: OpenStack',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX',
    ],
    license = 'APL 2.0',
)
