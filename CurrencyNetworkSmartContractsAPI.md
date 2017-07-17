## Smart Contract API

### `Exchange.sol`
This smart contract contains the main business logic. It is dependant on `PriceOracle.sol`, which is an Oracle for price feeds.
Other dependencies are for modularization purposes, we strictly followed the SoC-Patterns.

### Issue RFQ [SOU]: issueRFQ

+ Parameters
    + ContractType contractType - enum of contractTypes, converted to uint for external calls
    + ProductType productType - enum of productType, converted to uint for external calls
    + OrderType orderType - enum of orderType, converted to uint for external calls
    + KindType kindType - enum of kindType, defines Bid or Ask, converted to uint for external calls
    + int volume - volume of productType
    + uint8 period - period, specifying the productType for given time frame
    + uint price - price for Bid or Ask in currency
    + uint time - time in seconds from now for TimedRFQs
    + string unit - unit of volume
    + string currency - currency of price

+ Result on success

        event RFQIssued(all input parameters)
        event RFQMarketMatch(bytes32 rfqId)
        event RFQRestingMatch(bytes32 rfqId, bytes32 matchId, int volume, int storedVolume)
        event RFQPartialRestingMatch(bytes32 rfqId, bytes32 matchId, int volume, int storedVolume)

### Accept RFQ [PRM]: acceptRFQ

+ Parameters
    + bytes32 rfqId - ID of issued RFQ (derived in frontend application)
    + uint actualPrice - actual price which is set by PRM
    + uint hedgeFee - fee for hedging, set by PRM and currently fixed (0.5%)

+ Result on success

        event RFQAccepted(bytes32 rfqId)
        event RFQMarketMatch(bytes32 rfqId)
        event RFQRestingMatch(bytes32 rfqId, bytes32 matchId, int volume, int storedVolume)
        event RFQPartialRestingMatch(bytes32 rfqId, bytes32 matchId, int volume, int storedVolume)
        event RFQChanged(bytes32 rfqId, int volume, int storedVolume)
        event RFQRestingRemoved(bytes32 rfqId)
        event RFQCurrentRemoved(bytes32 rfqId)

### Counter RFQ [PRM]; counterRFQ

+ Parameters
    + bytes32 rfqId - ID of issued RFQ (derived in frontend application)
    + int volume - countered volume of productType
    + uint price - countered price for Bid or Ask in currency

### Update price for product and period, called from PriceOracle as Listener (Observer-Pattern)

### Set time of last order: setLastOrder()

+ No Parameters

+ Result on success: till restart/redeploy no order are accepted anymore

### Timer: do recurring work (for TimedRFQs and status changed MarketRFQs): tick()

+ No Parameters

+ Result on success

        event RFQRestingMatch(bytes32 rfqId, bytes32 matchId, int volume, int storedVolume)
        event RFQPartialRestingMatch(bytes32 rfqId, bytes32 matchId, int volume, int storedVolume)
        event RFQChanged(bytes32 rfqId, int volume, int storedVolume)
        event RFQRestingRemoved(bytes32 rfqId)
        event RFQCurrentRemoved(bytes32 rfqId)

### `PriceOracle.sol`
This smart contract is called by an external Python component, which feeds the current Market price data (mocked by example data in PoC).
The PriceOracle allows for Listeners, which get called back with new prices (`Exchange.sol` does register on construction as one Listener).

### Update Price from Market data feed (external process): updatePrice

+ Parameters
    + ProductType productType - product type for update
    + uint8 period - period for specifying product to update price
    + uint price - price for update

+ Result on success

        Internal update of product/period tuple
        Exchange.updatePrice(...) is called for the specified product

### Get current Market price for product and period: getPrice

+ Parameters
    + ProductType productType - product type for update
    + uint8 period - period for specifying product to update price

+ Result on success

        return price of product and period as set by last updatePrice
