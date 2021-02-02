import collections

from tlbin import load_packaged_contracts


# lazily load the contracts, so the compile_contracts fixture has a chance to
# set TRUSTLINES_CONTRACTS_JSON
class LazyContractsLoader(collections.UserDict):
    def __getitem__(self, *args):
        if not self.data:
            self.data = load_packaged_contracts()
        return super().__getitem__(*args)


contracts = LazyContractsLoader()


def get_contract_interface(contract_name):
    return contracts[contract_name]
