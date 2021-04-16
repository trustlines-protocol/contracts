# Py-Bin

This directory contains an npm and a python package used to pack the `contracts.json` and `merged_abis.json`
file containing among other things the abi and bytecode of all compiled contracts from this repository.

The `merged_abis.json` contains the merged abi of all the versions of currency networks. This is useful for currency
networks that use a proxy pattern and have been upgraded to different versions through their lifetime.

The `tlbin` python package can be used to easily load the `contracts.json` or `merged_abis.json` with the following:

```python
from tlbin import load_packaged_contracts, load_packaged_merged_abis

contracts_dict = load_packaged_contracts()
merged_abis_dict = load_packaged_merged_abis()
```
