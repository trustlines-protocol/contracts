import json

import pkg_resources


def load_packaged_contracts():
    with open(pkg_resources.resource_filename(__name__, "contracts.json")) as file:
        return json.load(file)
