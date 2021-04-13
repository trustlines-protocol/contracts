pragma solidity ^0.8.0;

import "./CurrencyNetworkV2.sol";
import "./CurrencyNetworkBasicV2.sol";

contract CurrencyNetworkOwnableV2 is CurrencyNetworkV2 {
    address public owner;

    event NetworkUnfreeze();
    event OwnerRemoval();

    /**
     * @dev Throws if called by any account other than the owner.
     */
    modifier onlyOwner() {
        require(owner == msg.sender, "Caller is not the owner");
        _;
    }

    function removeOwner() external onlyOwner {
        owner = address(0);
        emit OwnerRemoval();
    }

    /**
     * @dev Set an account for two users, the final balance will be
            _balance plus the interests accrued on _balance in between _mtime and now.
     * @param _creditor The first party of the trustline agreement
     * @param _debtor The other party of the trustline agreement
     * @param _creditlineGiven The creditline limit given by _creditor
     * @param _creditlineReceived The creditline limit given _debtor
     * @param _interestRateGiven The interest given by _creditor
     * @param _interestRateReceived The interest given by _debtor
     * @param _isFrozen Whether the trustline should be frozen
     * @param _mtime The last modification time of the balance
     * @param _balance The balance of the trustline at time _mtime as seen by _creditor
     */
    function setAccount(
        address _creditor,
        address _debtor,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived,
        int16 _interestRateGiven,
        int16 _interestRateReceived,
        bool _isFrozen,
        uint32 _mtime,
        int72 _balance
    ) external virtual onlyOwner {
        TrustlineAgreement memory trustlineAgreement;
        trustlineAgreement.creditlineGiven = _creditlineGiven;
        trustlineAgreement.creditlineReceived = _creditlineReceived;
        trustlineAgreement.interestRateGiven = _interestRateGiven;
        trustlineAgreement.interestRateReceived = _interestRateReceived;
        trustlineAgreement.isFrozen = _isFrozen;

        // We apply the interests and set mtime to now because it should match with
        // the time at which BalanceUpdate is emitted (e.g. to compute pending interests offchain)
        TrustlineBalances memory trustlineBalances;
        trustlineBalances.mtime = uint32(block.timestamp);
        int72 balanceWithInterests =
            calculateBalanceWithInterests(
                _balance,
                _mtime,
                block.timestamp,
                _interestRateGiven,
                _interestRateReceived
            );
        trustlineBalances.balance = balanceWithInterests;

        _storeTrustlineAgreement(_creditor, _debtor, trustlineAgreement);
        _storeTrustlineBalances(_creditor, _debtor, trustlineBalances);

        addToUsersAndFriends(_creditor, _debtor);
        emit TrustlineUpdate(
            _creditor,
            _debtor,
            _creditlineGiven,
            _creditlineReceived,
            _interestRateGiven,
            _interestRateReceived,
            _isFrozen
        );
        emit BalanceUpdate(_creditor, _debtor, balanceWithInterests);
    }

    /**
     * @dev Set a trustline request in between two users
     * @param _creditor The first party of the trustline request
     * @param _debtor The other party of the trustline request
     * @param _creditlineGiven The creditline limit given by _creditor
     * @param _creditlineReceived The creditline limit given _debtor
     * @param _interestRateGiven The interest given by _creditor
     * @param _interestRateReceived The interest given by _debtor
     * @param _isFrozen Whether the trustline should be frozen
     */
    function setTrustlineRequest(
        address _creditor,
        address _debtor,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived,
        int16 _interestRateGiven,
        int16 _interestRateReceived,
        bool _isFrozen
    ) external onlyOwner {
        _requestTrustlineUpdate(
            _creditor,
            _debtor,
            _creditlineGiven,
            _creditlineReceived,
            _interestRateGiven,
            _interestRateReceived,
            _isFrozen,
            0
        );
    }

    function setOnboarder(address user, address onBoarder) external onlyOwner {
        onboarder[user] = onBoarder;
        emit Onboard(onBoarder, user);
    }

    function setDebt(
        address debtor,
        address creditor,
        int256 value
    ) external onlyOwner {
        _addToDebt(debtor, creditor, value);
    }

    function unfreezeNetwork() external onlyOwner {
        require(isNetworkFrozen == true, "Network is not frozen");
        isNetworkFrozen = false;
        emit NetworkUnfreeze();
    }

    /**
     * @notice Initialize the currency Network
     * @param _name The name of the currency
     * @param _symbol The symbol of the currency
     * @param _decimals Number of decimals of the currency
     * @param _capacityImbalanceFeeDivisor Divisor of the imbalance fee. The fee is 1 / _capacityImbalanceFeeDivisor
     * @param _defaultInterestRate The default interests for every trustlines in 0.01% per year
     * @param _customInterests Flag to allow or disallow trustlines to have custom interests
     * @param _preventMediatorInterests Flag to allow or disallow transactions resulting in loss of interests for
     *         intermediaries, unless the transaction exclusively reduces balances
     * @param _expirationTime Time after which the currency network is frozen and cannot be used anymore. Setting
     *         this value to zero disables freezing.
     */
    function init(
        string memory _name,
        string memory _symbol,
        uint8 _decimals,
        uint16 _capacityImbalanceFeeDivisor,
        int16 _defaultInterestRate,
        bool _customInterests,
        bool _preventMediatorInterests,
        uint256 _expirationTime,
        address[] memory authorizedAddresses
    ) public virtual override {
        owner = msg.sender;
        isNetworkFrozen = true;
        CurrencyNetworkBasicV2.init(
            _name,
            _symbol,
            _decimals,
            _capacityImbalanceFeeDivisor,
            _defaultInterestRate,
            _customInterests,
            _preventMediatorInterests,
            _expirationTime,
            authorizedAddresses
        );
    }
}

// SPDX-License-Identifier: MIT
