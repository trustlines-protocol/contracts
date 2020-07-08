import json
import os
import sys


def load_packaged_contracts():
    with open(
        os.path.join(sys.prefix, "trustlines-contracts", "build", "contracts.json")
    ) as file:
        return json.load(file)
