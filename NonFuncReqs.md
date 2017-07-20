## Non-Functional Requirements

### Upgradeability

Strategies for upgradeable contracts include:

* https://github.com/ownage-ltd/ether-router/blob/master/contracts/EtherRouter.sol
* https://blog.colony.io/writing-upgradeable-contracts-in-solidity-6743f0eecc88
* https://gist.github.com/Arachnid/4ca9da48d51e23e5cfe0f0e14dd6318f
* https://ethereum.stackexchange.com/questions/21541/how-does-upgradeable-sol-work/21546#21546

#### Two strategies for updates

1. Use `DELEGATECALL`, keep storage in Dispatcher
2. Use very simple and _not_ upgradeable `EternalStorage` contract for storage, change its owner on update of using contract (ie. `CurrencyNetwork`)

#### Upgrade path for `CurrencyNetwork` contract

All relevant information is stored in the `Trustlines` struct which is used in `EternalStorage`.
This resembles strategy 2: using the more expensive but clearly defined `EternalStorage` contract for all data relevant a currency network.

If the `CurrencyNetwork` contract has to be updated, the following steps have to be processed for each currency network contract.

1. Deploy a new contract for each currency network, using `CurrencyNetworkFactory`
2. Call `EternalStorage.authorize(address user)` as the creator of the new CurrencyFactory
3. `CurrencyNetworkFactory` makes sure that the `EternalStorage` given at address `reuseStorage` of the parameters of `createCurrencyNetwork` factory function is set to the new `CurrencyNetwork` address.

After step 3 the new `CurrencyNetwork` is the only legitimate user of the existing `EternalStorage`.