# -*- coding: utf-8 -*-

from codecs import open

try:
    from setuptools import setup
except:
    raise ImportError("setuptools is required ...")


def parse_requires(_list):
    requires = list()
    trims = ["#", "piwheels.org"]
    for require in _list:
        if any(match in require for match in trims):
            continue
        requires.append(require)
    requires = list(filter(None, requires))  # remove "" from list
    return requires


with open("requirements.txt") as f:
    requirements = f.read().splitlines()

requires = parse_requires(requirements)


setup(
    name="spectool-client-parser",
    version="1.0.0",
    description="wispy plugin for wlanpi-grafana",
    license="BSD-3-Clause",
    classifiers=[
        "Natural Language :: English",
        "Intended Audience :: System Administrators",
        "Topic :: Utilities",
    ],
    packages=['wispy'],
    project_urls={
        "Documentation": "https://docs.wlanpi.com",
        "Source": "https://github.com/wlan-pi/wlanpi-grafana",
    },
    include_package_data=True,
    install_requires=requires,
    entry_points = {
        'console_scripts': ['spectool-client-parser=wispy.spectool_client_parser:main'],
    },
)
