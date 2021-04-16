import json

import pkg_resources


def load_packaged_contracts():
    with open(pkg_resources.resource_filename(__name__, "contracts.json")) as file:
        return json.load(file)


def load_packaged_merged_abis():
    with open(pkg_resources.resource_filename(__name__, "merged_abis.json")) as file:
        return json.load(file)
