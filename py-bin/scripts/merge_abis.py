import json


def create_merged_abi(
    legacy_networks_filename, recent_networks_filename, output_filename
):
    with open(legacy_networks_filename) as f:
        legacy_contracts_dict = json.load(f)
    with open(recent_networks_filename) as f:
        recent_contracts_dict = json.load(f)

    merged_abi = (
        legacy_contracts_dict["CurrencyNetworkOwnable"]["abi"]
        + recent_contracts_dict["CurrencyNetworkOwnableV2"]["abi"]
    )

    output = {"MergedCurrencyNetworksAbi": {"abi": merged_abi}}

    with open(output_filename, "w") as f:
        json.dump(output, f, indent=2)


if __name__ == "__main__":
    import sys

    create_merged_abi(sys.argv[1], sys.argv[2], sys.argv[3])
