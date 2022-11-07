import json

import pkg_resources


def load_packaged_contracts():
    with open(pkg_resources.resource_filename(__name__, "contracts.json")) as file:
        contracts = json.load(file)
    with open(
        pkg_resources.resource_filename(__name__, "gnosis_safe_contracts.json")
    ) as file:
        gnosis_contracts = json.load(file)

    if any(
        contracts[k] != gnosis_contracts[k]
        for k in contracts.keys() & gnosis_contracts.keys()
    ):
        raise Exception(
            "contracts.json and gnosis_safe_contracts.json have conflicting keys"
        )
    else:
        return {**contracts, **gnosis_contracts}


def load_packaged_gnosis_safe_contracts():
    with open(
        pkg_resources.resource_filename(__name__, "gnosis_safe_contracts.json")
    ) as file:
        return json.load(file)


def load_packaged_merged_abis():
    with open(pkg_resources.resource_filename(__name__, "merged_abis.json")) as file:
        return json.load(file)
