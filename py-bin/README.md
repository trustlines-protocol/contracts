# Py-Bin

This directory contains an npm and a python package used to pack the `contracts.json`
file containing among other things the abi and bytecode of all compiled contracts from this repository.

The `tlbin` python package can be used to easily load the `contracts.json` with the following:

```python
from tlbin import load_packaged_contracts

contracts_dict = load_packaged_contracts()
```
