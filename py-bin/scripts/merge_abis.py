import json


def create_merged_abi(
    legacy_networks_filename, recent_networks_filename, output_filename
):
    with open(legacy_networks_filename) as f:
        legacy_contracts_dict = json.load(f)
    with open(recent_networks_filename) as f:
        recent_contracts_dict = json.load(f)

    recent_abis = recent_contracts_dict["CurrencyNetworkOwnableV2"]["abi"]
    legacy_abis = legacy_contracts_dict["CurrencyNetworkOwnable"]["abi"]
    proxy_abis = recent_contracts_dict["AdministrativeProxy"]["abi"]

    merged_abis = merge_abis(proxy_abis, recent_abis)
    merged_abis = merge_abis(merged_abis, legacy_abis)

    output = {"MergedCurrencyNetworksAbi": {"abi": merged_abis}}

    with open(output_filename, "w") as f:
        json.dump(output, f, indent=2)


def merge_abis(abis_1, abis_2):
    """
    Merge abis from abis_2 to abis_1, on conflicting abi keep abi from abis_1
    e.g. it will keep constructor, fallback, and receive abis from abi_1 if also present on abi_1
    """

    merged_abis = abis_1.copy()

    # We need to remove every abi that have the same selector (= signature) otherwise some tools will find it invalid
    for abi_2 in abis_2:

        if abi_2["type"] == "fallback":
            continue

        found_clashing_abi = False
        for abi_1 in abis_1:
            if abi_1["type"] == "fallback":
                continue
            if abi_signatures_clash(abi_1, abi_2):
                found_clashing_abi = True
                break

        if found_clashing_abi:
            continue
        merged_abis.append(abi_2)

    return merged_abis


def abi_signatures_clash(abi_1, abi_2):
    if "name" not in abi_1.keys() or "name" not in abi_2.keys():
        if abi_1["type"] == abi_2["type"]:
            assert abi_1["type"] in [
                "constructor",
                "receive",
                "fallback",
            ], "Found clashing abi with no name and unexpected type"
            return True
        return False
    return abi_1["name"] == abi_2["name"] and set(
        [abi_input["type"] for abi_input in abi_1["inputs"]]
    ) == set([abi_input["type"] for abi_input in abi_2["inputs"]])


if __name__ == "__main__":
    import sys

    create_merged_abi(sys.argv[1], sys.argv[2], sys.argv[3])
