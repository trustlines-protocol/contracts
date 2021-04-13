pragma solidity ^0.8.0;

import "../../lib/it_set_lib.sol";
import "../../lib/Authorizable.sol";
import "../../lib/ERC165.sol";
import "../CurrencyNetworkInterface.sol";

/**
 * @title Basic functionalities of Currency Networks
 * @notice Main contract of Trustlines, encapsulates all trustlines of one currency network.
 * Implements core features of currency networks related to opening / closing trustline and transfers.
 * Also includes freezing of TL / currency networks, interests and fees.
 **/
contract CurrencyNetworkBasicV2 is
    CurrencyNetworkInterface,
    Authorizable,
    ERC165
{
    // Constants
    int72 constant MAX_BALANCE = 2**64 - 1;
    int72 constant MIN_BALANCE = -MAX_BALANCE;
    int256 constant SECONDS_PER_YEAR = 60 * 60 * 24 * 365;

    using ItSet for ItSet.AddressSet;
    mapping(bytes32 => Trustline) internal trustlines;
    // mapping uniqueId => trustline request
    mapping(bytes32 => TrustlineRequest) internal requestedTrustlineUpdates;

    // friends, users address has a trustline with
    mapping(address => ItSet.AddressSet) internal friends;
    // list of all users of the system
    ItSet.AddressSet internal users;

    bool public isInitialized;
    uint256 public expirationTime;
    bool public isNetworkFrozen;

    // Divides current value being transferred to calculate the capacity fee which equals the imbalance fee
    uint16 public capacityImbalanceFeeDivisor;

    // interests settings, interests are expressed in 0.01% per year
    int16 public defaultInterestRate;
    bool public customInterests;
    bool public preventMediatorInterests;

    // Meta data
    string public override name;
    string public override symbol;
    uint8 public override decimals;

    // Events
    // Transfer event defined in CurrencyNetworkInterface
    event TrustlineUpdateRequest(
        address indexed _creditor,
        address indexed _debtor,
        uint256 _creditlineGiven,
        uint256 _creditlineReceived,
        int256 _interestRateGiven,
        int256 _interestRateReceived,
        bool _isFrozen,
        int72 _transfer
    );

    event TrustlineUpdate(
        address indexed _creditor,
        address indexed _debtor,
        uint256 _creditlineGiven,
        uint256 _creditlineReceived,
        int256 _interestRateGiven,
        int256 _interestRateReceived,
        bool _isFrozen
    );

    event TrustlineUpdateCancel(
        address indexed _initiator,
        address indexed _counterparty
    );

    event BalanceUpdate(
        address indexed _from,
        address indexed _to,
        int256 _value
    );

    event NetworkFreeze();

    // for accounting balance and trustline agreement between two users introducing fees and interests
    // currently uses 160 + 136 bits, 216 remaining to make two structs
    struct Trustline {
        // A < B (A is the lower address)
        TrustlineAgreement agreement;
        TrustlineBalances balances;
    }

    struct TrustlineAgreement {
        uint64 creditlineGiven; //  creditline given by A to B, always positive
        uint64 creditlineReceived; //  creditline given by B to A, always positive
        int16 interestRateGiven; //  interest rate set by A for creditline given by A to B in 0.01% per year
        int16 interestRateReceived; //  interest rate set by B for creditline given from B to A in 0.01% per year
        bool isFrozen; //  8 bits
    }

    struct TrustlineBalances {
        uint32 mtime; //  last time interests were applied
        int72 balance; //  balance between A and B, balance is >0 if B owes A, negative otherwise.
        //  balance(B,A) = - balance(A,B)
    }

    struct TrustlineRequest {
        uint64 creditlineGiven;
        uint64 creditlineReceived;
        int16 interestRateGiven;
        int16 interestRateReceived;
        bool isFrozen;
        address initiator;
        int72 transfer; // Transfer to apply when trustline is first open
    }

    constructor() {
        // solium-disable-previous-line no-empty-blocks
        // don't do anything here due to upgradeability issues (no constructor-call on replacement).
    }

    fallback() external {}

    /**
     * @notice send `_value` along `_path`
     * The fees will be payed by the sender, so `_value` is the amount received by receiver
     * @param _value The amount to be transferred
     * @param _maxFee Maximum fee the sender wants to pay
     * @param _path Path of transfer starting with msg.sender and ending with receiver
     * @param _extraData extra data bytes to be logged in the Transfer event
     **/
    function transfer(
        uint64 _value,
        uint64 _maxFee,
        address[] calldata _path,
        bytes calldata _extraData
    ) external override {
        require(
            _path.length > 0 && msg.sender == _path[0],
            "The path must start with msg.sender"
        );
        _mediatedTransferSenderPays(_value, _maxFee, _path, _extraData);
    }

    /**
     * @notice send `_value` along `_path`
     * msg.sender needs to be authorized to call this function
     * @param _value The amount of token to be transferred
     * @param _maxFee Maximum fee the sender wants to pay
     * @param _path Path of transfer starting with sender and ending with receiver
     * @param _extraData extra data bytes to be logged in the Transfer event
     **/
    function transferFrom(
        uint64 _value,
        uint64 _maxFee,
        address[] calldata _path,
        bytes calldata _extraData
    ) external override {
        require(
            globalAuthorized[msg.sender] ||
                (_path.length > 0 && authorizedBy[_path[0]][msg.sender]),
            "The sender of the message is not authorized."
        );

        _mediatedTransferSenderPays(_value, _maxFee, _path, _extraData);
    }

    /**
     * @notice send `_value` along `_path`
     * The fees will be payed by the receiver, so `_value` is the amount that is sent out by sender
     * @param _value The amount of token to be transferred
     * @param _maxFee Maximum fee the sender wants to pay
     * @param _path Path of transfer starting with msg.sender and ending with receiver
     * @param _extraData extra data bytes to be logged in the Transfer event
     **/
    function transferReceiverPays(
        uint64 _value,
        uint64 _maxFee,
        address[] calldata _path,
        bytes calldata _extraData
    ) external {
        require(
            _path.length > 0 && msg.sender == _path[0],
            "The path must start with msg.sender"
        );
        _mediatedTransferReceiverPays(_value, _maxFee, _path, _extraData);
    }

    /**
     * @notice `msg.sender` offers a trustline update to `_debtor` of `_creditlineGiven` tokens for `_creditlineReceived`
     * token
     * Needs to be accepted by the other party, unless we reduce both values.
     * @param _debtor The other party of the trustline agreement
     * @param _creditlineGiven The creditline limit given by msg.sender
     * @param _creditlineReceived The creditline limit given _debtor
     * @param _interestRateGiven The interest given by msg.sender
     * @param _interestRateReceived The interest given by _debtor
     * @param _isFrozen Whether the initiator asks for freezing the trustline
     */
    function updateTrustline(
        address _debtor,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived,
        int16 _interestRateGiven,
        int16 _interestRateReceived,
        bool _isFrozen
    ) external {
        address _creditor = msg.sender;

        _updateTrustline(
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

    /**
     * @notice `msg.sender` offers a trustline update to `_debtor` of `_creditlineGiven` tokens for `_creditlineReceived`
     * token
     * Needs to be accepted by the other party, unless we reduce both values.
     * @param _debtor The other party of the trustline agreement
     * @param _creditlineGiven The creditline limit given by msg.sender
     * @param _creditlineReceived The creditline limit given _debtor
     * @param _interestRateGiven The interest given by msg.sender
     * @param _interestRateReceived The interest given by _debtor
     * @param _isFrozen Whether the initiator asks for freezing the trustline
     * @param _transfer To apply a transfer when the trustline is accepted, >0 for a transfer from msg.sender to _debtor, <0 for the other way around
     */
    function updateTrustline(
        address _debtor,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived,
        int16 _interestRateGiven,
        int16 _interestRateReceived,
        bool _isFrozen,
        int72 _transfer
    ) external {
        address _creditor = msg.sender;

        require(
            !friends[_creditor].contains(_debtor),
            "A trustline already exists"
        );
        require(MIN_BALANCE <= _transfer, "Transfer exceeds min balance");
        require(MAX_BALANCE >= _transfer, "Transfer exceeds max balance");

        _updateTrustline(
            _creditor,
            _debtor,
            _creditlineGiven,
            _creditlineReceived,
            _interestRateGiven,
            _interestRateReceived,
            _isFrozen,
            _transfer
        );
    }

    /**
     * @notice Updates the balance of the trustline between `msg.sender` and `_counterParty`
        by applying the outstanding interests
        @param _counterParty The counterparty with which to update the interests
     */
    function applyInterests(address _counterParty) external {
        Trustline memory trustline = _loadTrustline(msg.sender, _counterParty);
        require(
            !_isTrustlineFrozen(trustline.agreement),
            "Cannot apply interests, the trustline is frozen"
        );
        _applyInterests(trustline);
        emit BalanceUpdate(
            msg.sender,
            _counterParty,
            trustline.balances.balance
        );
        _storeTrustlineBalances(msg.sender, _counterParty, trustline.balances);
    }

    /**
     * @notice `msg.sender` cancels a trustline update it initiated with _debtor
     * @param _counterparty The other party of the trustline agreement
     */
    function cancelTrustlineUpdate(address _counterparty) external {
        require(
            !isNetworkFrozen,
            "The network is frozen; trustlines update cannot be canceled."
        );

        TrustlineRequest memory trustlineRequest =
            _loadTrustlineRequest(msg.sender, _counterparty);
        require(
            trustlineRequest.initiator != address(0),
            "No request to delete."
        );
        _deleteTrustlineRequest(msg.sender, _counterparty);

        emit TrustlineUpdateCancel(msg.sender, _counterparty);
    }

    /**
     * @notice `msg.sender` offers a trustline update to `_debtor` of `_creditlineGiven` tokens for `_creditlineReceived`
     * token
     * Needs to be accepted by the other party, unless we reduce both values.
     * @param _debtor The other party of the trustline agreement
     * @param _creditlineGiven The creditline limit given by msg.sender
     * @param _creditlineReceived The creditline limit given _debtor
     */
    function updateCreditlimits(
        address _debtor,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived
    ) external {
        address _creditor = msg.sender;

        _updateCreditlimits(
            _creditor,
            _debtor,
            _creditlineGiven,
            _creditlineReceived
        );
    }

    /**
     * @notice `msg.sender` closes a trustline with `_otherParty`
     * For this to succeed the balance of this trustline needs to be zero
     * @param _otherParty The other party of the trustline agreement
     */
    function closeTrustline(address _otherParty) external {
        address from = msg.sender;

        _closeTrustline(from, _otherParty);
    }

    /** @notice Close the trustline between `msg.sender` and `_otherParty`
                by doing a transfer from msg.sender to _otherParty to bring balance to zero
        @param _otherParty Address of the other party to close the trustline with
        @param _minBalance The maximum balance the trustline should have to close it
        @param _maxBalance The minimum balance the trustline should have to close it
     */
    function closeTrustlineByDirectTransfer(
        address _otherParty,
        uint64 _minBalance,
        uint64 _maxBalance
    ) external {
        // We load the trustline in the view of msg.sender, the balance is what msg.sender has to send to _otherParty
        Trustline memory trustline = _loadTrustline(msg.sender, _otherParty);
        _applyInterests(trustline);
        require(
            trustline.balances.balance <= _maxBalance,
            "Balance on trustline exceeds _maxBalance"
        );
        require(
            trustline.balances.balance >= _minBalance,
            "Balance on trustline exceeds _minBalance"
        );

        address[] memory path = new address[](2);
        path[0] = msg.sender;
        path[1] = _otherParty;

        _mediatedTransferSenderPays(
            uint64(uint72(trustline.balances.balance)),
            0,
            path,
            ""
        );

        _closeTrustline(msg.sender, _otherParty);
    }

    /** @notice Close the trustline between `msg.sender` and `_otherParty` by doing a triangular transfer over `_path
        @param _otherParty Address of the other party to close the trustline with
        @param _maxFee maximum fees the sender is willing to pay
        @param _path The path along, which to do the triangulation
     */
    function closeTrustlineByTriangularTransfer(
        address _otherParty,
        uint64 _maxFee,
        address[] calldata _path
    ) external {
        _closeTrustlineByTriangularTransfer(_otherParty, _maxFee, _path);
    }

    /**
     * @notice Query the trustline between two users.
     * @param _a First address that defines the trustline
     * @param _b second address that defines the trustline
     * @dev Can be removed once structs are supported in the ABI
     */
    function getAccount(address _a, address _b)
        external
        view
        returns (
            int256,
            int256,
            int256,
            int256,
            bool,
            int256,
            int256
        )
    {
        Trustline memory trustline = _loadTrustline(_a, _b);

        return (
            trustline.agreement.creditlineGiven,
            trustline.agreement.creditlineReceived,
            trustline.agreement.interestRateGiven,
            trustline.agreement.interestRateReceived,
            trustline.agreement.isFrozen || isNetworkFrozen,
            trustline.balances.mtime,
            trustline.balances.balance
        );
    }

    /**
     * @notice Freezes the network once the expirationTime has been reached
     * it can no longer be used after that
     **/
    function freezeNetwork() external {
        require(
            expirationTime != 0,
            "The currency network has disabled freezing."
        );
        require(
            expirationTime <= block.timestamp,
            "The currency network cannot be frozen yet."
        );
        isNetworkFrozen = true;
        emit NetworkFreeze();
    }

    /**
     * @notice Queries whether the contract supports the given interfaceID (see ERC165)
     * @param interfaceID the queried interface id
     * @return A boolean for whether the interface id is supported
     * @dev This needs to be in sync with CurrencyNetworkInterface.sol
     **/
    function supportsInterface(bytes4 interfaceID)
        external
        pure
        override
        returns (bool)
    {
        return (interfaceID == this.supportsInterface.selector || // ERC165
            (// This needs to be in sync with CurrencyNetworkInterface.sol
            interfaceID ==
                (this.name.selector ^
                    this.symbol.selector ^
                    this.decimals.selector ^
                    this.transfer.selector ^
                    this.transferFrom.selector ^
                    this.balance.selector ^
                    this.creditline.selector)));
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
    ) public virtual {
        require(!isInitialized, "Currency Network already initialized.");
        isInitialized = true;

        // verifies that only one parameter is selected.
        require(
            !((_defaultInterestRate != 0) && _customInterests),
            "Custom interests are set; default interest rate must be zero."
        );
        require(
            _defaultInterestRate <= 2000 && _defaultInterestRate >= -2000,
            "Default interests cannot exceed +-20%."
        );
        require(
            !_preventMediatorInterests ||
                (_preventMediatorInterests && _customInterests),
            "Prevent mediator interest cannot be set without using custom interests."
        );

        require(
            _expirationTime == 0 || _expirationTime > block.timestamp,
            "Expiration time must be either in the future or zero to disable it."
        );

        require(
            _capacityImbalanceFeeDivisor != 1,
            "Too low imbalance fee divisor, fees can not be more than 50%"
        );

        name = _name;
        symbol = _symbol;
        decimals = _decimals;
        capacityImbalanceFeeDivisor = _capacityImbalanceFeeDivisor;
        defaultInterestRate = _defaultInterestRate;
        customInterests = _customInterests;
        preventMediatorInterests = _preventMediatorInterests;
        expirationTime = _expirationTime;

        for (uint256 i = 0; i < authorizedAddresses.length; i++) {
            addGlobalAuthorizedAddress(authorizedAddresses[i]);
        }
    }

    /**
     * @notice The creditline limit given by `_creditor` to `_debtor`
     * @param _creditor the creditor of the queried trustline
     * @param _debtor the debtor of the queried trustline
     * @return _creditline credit limit given by creditor to debtor
     */
    function creditline(address _creditor, address _debtor)
        public
        view
        override
        returns (uint256 _creditline)
    {
        // returns the current creditline given by A to B
        TrustlineAgreement memory trustlineAgreement =
            _loadTrustlineAgreement(_creditor, _debtor);
        _creditline = trustlineAgreement.creditlineGiven;
    }

    /**
     * @notice The interest rate given by `_creditor` to `_debtor`
     * @param _creditor the creditor of the queried trustline
     * @param _debtor the debtor of the queried trustline
     * @return _interestRate Interest rate given by creditor to debtor on the balance of the line
     */
    function interestRate(address _creditor, address _debtor)
        public
        view
        returns (int16 _interestRate)
    {
        // returns the current interests given by A to B
        TrustlineAgreement memory trustlineAgreement =
            _loadTrustlineAgreement(_creditor, _debtor);
        _interestRate = trustlineAgreement.interestRateGiven;
    }

    /**
     * @notice returns what _b owes to _a
     * @param _a First address that defines the trustline
     * @param _b second address that defines the trustline
     * @return _balance the amount _b owes to _a on the trustline between _a and _b
     **/
    function balance(address _a, address _b)
        public
        view
        override
        returns (int256 _balance)
    {
        TrustlineBalances memory trustlineBalances =
            _loadTrustlineBalances(_a, _b);
        _balance = trustlineBalances.balance;
    }

    /**
     * @notice returns the list of friends of _user,
     * that is the list of addresses with which _user has an open trustline
     * @param _user The user to query the list of friends for
     **/
    function getFriends(address _user) public view returns (address[] memory) {
        return friends[_user].list;
    }

    /**
     * @notice returns the list of all the users of trustlines,
     * that is all the addresses that ever opened a trustline
     **/
    function getUsers() public view returns (address[] memory) {
        return users.list;
    }

    function isTrustlineFrozen(address a, address b)
        public
        view
        returns (bool)
    {
        if (isNetworkFrozen) {
            return true;
        }
        TrustlineAgreement memory trustlineAgreement =
            _loadTrustlineAgreement(a, b);
        return trustlineAgreement.isFrozen;
    }

    // This function will calculate the compound interests with a Taylor approximation
    // It will give correct results if: rate * (_endTime - _startTime) < 10_000 * SECONDS_PER_YEAR
    // so that Balance(t) = Balance(0) * exp(r*t) where (r*t) < 1
    function calculateBalanceWithInterests(
        int72 _balance,
        uint256 _startTime,
        uint256 _endTime,
        int16 _interestRateGiven,
        int16 _interestRateReceived
    ) public pure returns (int72) {
        require(
            _balance <= MAX_BALANCE && _balance >= MIN_BALANCE,
            "The function requires the _balance to fit into a 64 bit value"
        );
        require(_startTime <= _endTime, "_startTime should be before _endTime");
        int16 rate = 0;
        if (_balance > 0) {
            rate = _interestRateGiven;
        } else if (_balance < 0) {
            rate = _interestRateReceived;
        }

        if (rate == 0) {
            return _balance;
        }

        int256 dt = int256(_endTime - _startTime);
        int256 intermediateOrder = _balance;
        int256 newBalance = _balance;

        assert(dt >= 0);

        for (int256 i = 1; i <= 15; i++) {
            int256 newIntermediateOrder = intermediateOrder * rate * dt;

            //Overflow adjustment
            if (
                (newIntermediateOrder != 0) &&
                (newIntermediateOrder / (rate * dt) != intermediateOrder)
            ) {
                if (rate > 0) {
                    if (_balance > 0) {
                        newBalance = MAX_BALANCE;
                    } else {
                        newBalance = MIN_BALANCE;
                    }
                } else {
                    newBalance = 0;
                }
                break;
            }

            intermediateOrder =
                newIntermediateOrder /
                (SECONDS_PER_YEAR * 10000 * i);

            if (intermediateOrder == 0) {
                break;
            }

            int256 oldBalance = newBalance;
            newBalance += intermediateOrder;

            // overflow check of newBalance
            if (oldBalance > 0 && intermediateOrder > 0) {
                if (newBalance <= 0) {
                    newBalance = oldBalance;
                    break;
                }
            }
            if (oldBalance < 0 && intermediateOrder < 0) {
                if (newBalance >= 0) {
                    newBalance = oldBalance;
                    break;
                }
            }
        }

        // Restrict balance within MAX / MIN balance
        // If rate is negative, we assume that the balance was eventually going to be 0
        if (rate > 0) {
            if (newBalance > MAX_BALANCE) {
                newBalance = MAX_BALANCE;
            }
            if (newBalance < MIN_BALANCE) {
                newBalance = MIN_BALANCE;
            }
        }
        if (rate < 0) {
            if (_balance > 0 && newBalance > _balance) {
                newBalance = 0;
            }
            if (_balance < 0 && newBalance < _balance) {
                newBalance = 0;
            }
        }
        // If sign flipped because of wrong calculation, the best thing we can do is to assume the result should be 0
        if (newBalance * _balance < 0) {
            newBalance = 0;
        }

        return int72(newBalance);
    }

    // This function transfers value over this trustline
    // For that it modifies the value of the balance stored in the trustline for sender and receiver
    function _applyDirectTransfer(Trustline memory _trustline, uint64 _value)
        internal
        pure
    {
        int72 newBalance = _trustline.balances.balance - _value;

        // check if creditline is not exceeded
        uint64 creditlineReceived = _trustline.agreement.creditlineReceived;
        require(
            -newBalance <= creditlineReceived,
            "The transferred value exceeds the capacity of the credit line."
        );

        _trustline.balances.balance = newBalance;
    }

    function _applyInterests(Trustline memory _trustline) internal view {
        _trustline.balances.balance = calculateBalanceWithInterests(
            _trustline.balances.balance,
            _trustline.balances.mtime,
            block.timestamp,
            _trustline.agreement.interestRateGiven,
            _trustline.agreement.interestRateReceived
        );
        // Fine until 2106
        _trustline.balances.mtime = uint32(block.timestamp);
    }

    function _mediatedTransferSenderPays(
        uint64 _value,
        uint64 _maxFee,
        address[] memory _path,
        bytes memory _extraData
    ) internal {
        require(_path.length > 1, "Path too short.");

        uint64 forwardedValue = _value;
        uint64 fees = 0;
        int256 receiverUnhappiness = 0;
        int256 receiverHappiness = 0;
        bool reducingDebtOfNextHopOnly = true;

        // check path in reverse to correctly accumulate the fee
        for (
            uint256 receiverIndex = _path.length - 1;
            receiverIndex > 0;
            receiverIndex--
        ) {
            address receiver = _path[receiverIndex];
            address sender = _path[receiverIndex - 1];

            uint64 fee;

            // Load trustline only once at the beginning
            Trustline memory trustline = _loadTrustline(sender, receiver);
            require(
                !_isTrustlineFrozen(trustline.agreement),
                "The path given is incorrect: one trustline in the path is frozen."
            );
            _applyInterests(trustline);

            if (receiverIndex == _path.length - 1) {
                fee = 0; // receiver should not get a fee
            } else {
                fee = _calculateFeesReverse(
                    _calculateImbalanceGenerated(
                        forwardedValue,
                        trustline.balances.balance
                    ),
                    capacityImbalanceFeeDivisor
                );
            }

            // forward the value + the fee
            forwardedValue = forwardedValue + fee;
            fees = fees + fee;
            require(fees <= _maxFee, "The fees exceed the max fee parameter.");

            int72 balanceBefore = trustline.balances.balance;

            _applyDirectTransfer(trustline, forwardedValue);

            if (preventMediatorInterests) {
                // prevent intermediaries from paying more interests than they receive
                // unless the transaction helps in reducing the debt of the next hop in the path
                receiverHappiness = receiverUnhappiness; // receiver was the sender in last iteration
                receiverUnhappiness = _interestHappiness(
                    trustline,
                    balanceBefore
                );
                require(
                    receiverUnhappiness <= receiverHappiness ||
                        reducingDebtOfNextHopOnly,
                    "The transfer was prevented by the prevent mediator interests strategy"
                );
                reducingDebtOfNextHopOnly = trustline.balances.balance >= 0;
            }

            // store only balance because trustline agreement did not change
            _storeTrustlineBalances(sender, receiver, trustline.balances);
            // The BalanceUpdate always has to be in the transfer direction
            emit BalanceUpdate(sender, receiver, trustline.balances.balance);
        }

        emit Transfer(_path[0], _path[_path.length - 1], _value, _extraData);
    }

    /* like _mediatedTransfer only the receiver pays
       which means we start walking the _path at the sender and substract fees from the forwarded value
    */
    function _mediatedTransferReceiverPays(
        uint64 _value,
        uint64 _maxFee,
        address[] memory _path,
        bytes memory _extraData
    ) internal {
        require(_path.length > 1, "Path too short.");

        uint64 forwardedValue = _value;
        uint64 fees = 0;
        int256 senderHappiness = -2**255;
        int256 senderUnhappiness = -2**255;
        bool reducingDebtOnly = true;

        // check path starting from sender correctly accumulate the fee
        for (
            uint256 senderIndex = 0;
            senderIndex < _path.length - 1;
            senderIndex++
        ) {
            address receiver = _path[senderIndex + 1];
            address sender = _path[senderIndex];

            uint64 fee;

            // Load trustline only once at the beginning
            Trustline memory trustline = _loadTrustline(sender, receiver);
            require(
                !_isTrustlineFrozen(trustline.agreement),
                "The path given is incorrect: one trustline in the path is frozen."
            );
            _applyInterests(trustline);

            int72 balanceBefore = trustline.balances.balance;

            _applyDirectTransfer(trustline, forwardedValue);

            if (preventMediatorInterests) {
                // prevent intermediaries from paying more interests than they receive
                // unless the transaction helps in reducing the debt of the next hop in the path
                senderUnhappiness = senderHappiness; // sender was the receiver in last iteration
                senderHappiness = _interestHappiness(trustline, balanceBefore);
                reducingDebtOnly = trustline.balances.balance >= 0;
                require(
                    senderHappiness >= senderUnhappiness || reducingDebtOnly,
                    "The transfer was prevented by the prevent mediator interests strategy"
                );
            }

            // store only balance because trustline agreement did not change
            _storeTrustlineBalances(sender, receiver, trustline.balances);
            // The BalanceUpdate always has to be in the transfer direction
            emit BalanceUpdate(sender, receiver, trustline.balances.balance);

            if (senderIndex == _path.length - 2) {
                break; // receiver is not a mediator, so no fees
            }

            // calculate fees for next mediator
            fee = _calculateFees(
                _calculateImbalanceGenerated(forwardedValue, balanceBefore),
                capacityImbalanceFeeDivisor
            );
            // Underflow check
            forwardedValue = forwardedValue - fee;

            fees = fees + fee;
            require(fees <= _maxFee, "The fees exceed the max fee parameter.");
        }

        emit Transfer(_path[0], _path[_path.length - 1], _value, _extraData);
    }

    /* close a trustline, which must have a balance of zero */
    function _closeTrustline(address _from, address _otherParty) internal {
        TrustlineBalances memory balances =
            _loadTrustlineBalances(_from, _otherParty);
        require(
            balances.balance == 0,
            "A trustline can only be closed if its balance is zero."
        );
        require(
            !isTrustlineFrozen(_from, _otherParty),
            "The trustline is frozen and cannot be closed."
        );

        bytes32 uniqueId = uniqueIdentifier(_from, _otherParty);
        delete requestedTrustlineUpdates[uniqueId];
        delete trustlines[uniqueId];
        friends[_from].remove(_otherParty);
        friends[_otherParty].remove(_from);
        emit TrustlineUpdate(_from, _otherParty, 0, 0, 0, 0, false);
    }

    function _closeTrustlineByTriangularTransfer(
        address _otherParty,
        uint64 _maxFee,
        address[] memory _path
    ) internal {
        require(_path.length >= 3, "Path given too short to be correct.");
        require(msg.sender == _path[0], "Path must start msg.sender.");
        require(
            msg.sender == _path[_path.length - 1],
            "Last element of path does not match msg.sender."
        );

        Trustline memory trustline = _loadTrustline(_path[0], _otherParty);
        require(
            !_isTrustlineFrozen(trustline.agreement),
            "The trustline is frozen and cannot be closed."
        );
        _applyInterests(trustline);
        TrustlineBalances memory balances = trustline.balances;

        if (balances.balance > 0) {
            require(
                _path[1] == _otherParty,
                "Second element of path does not match _otherParty address."
            );
            require(
                uint64(uint72(balances.balance)) == balances.balance,
                "Cannot transfer too high values."
            );
            _mediatedTransferReceiverPays(
                uint64(uint72(balances.balance)),
                _maxFee,
                _path,
                ""
            );
        } else if (balances.balance < 0) {
            require(
                _path[_path.length - 2] == _otherParty,
                "Second to last element of path does not match _otherParty address."
            );
            require(
                uint64(uint72(-balances.balance)) == -balances.balance,
                "Cannot transfer too high values."
            );
            _mediatedTransferSenderPays(
                uint64(uint72(-balances.balance)),
                _maxFee,
                _path,
                ""
            );
        } // else {} /* balance is zero, there's nothing to do here */

        _closeTrustline(_path[0], _otherParty);
    }

    function addToUsersAndFriends(address _a, address _b) internal {
        users.insert(_a);
        users.insert(_b);
        friends[_a].insert(_b);
        friends[_b].insert(_a);
    }

    function _loadTrustline(address _a, address _b)
        internal
        view
        returns (Trustline memory)
    {
        Trustline memory trustline;
        trustline.agreement = _loadTrustlineAgreement(_a, _b);
        trustline.balances = _loadTrustlineBalances(_a, _b);
        return trustline;
    }

    function _loadTrustlineAgreement(address _a, address _b)
        internal
        view
        returns (TrustlineAgreement memory)
    {
        TrustlineAgreement memory trustlineAgreement =
            trustlines[uniqueIdentifier(_a, _b)].agreement;
        TrustlineAgreement memory result;
        if (_a < _b) {
            result = trustlineAgreement;
        } else {
            result.creditlineReceived = trustlineAgreement.creditlineGiven;
            result.creditlineGiven = trustlineAgreement.creditlineReceived;
            result.interestRateReceived = trustlineAgreement.interestRateGiven;
            result.interestRateGiven = trustlineAgreement.interestRateReceived;
            result.isFrozen = trustlineAgreement.isFrozen;
        }
        return result;
    }

    function _loadTrustlineBalances(address _a, address _b)
        internal
        view
        returns (TrustlineBalances memory)
    {
        TrustlineBalances memory balances =
            trustlines[uniqueIdentifier(_a, _b)].balances;
        TrustlineBalances memory result;
        if (_a < _b) {
            result = balances;
        } else {
            result.mtime = balances.mtime;
            result.balance = -balances.balance;
        }
        return result;
    }

    // Provides the abstraction of whether a < b or b < a.
    function _storeTrustlineAgreement(
        address _a,
        address _b,
        TrustlineAgreement memory trustlineAgreement
    ) internal {
        if (!customInterests) {
            assert(trustlineAgreement.interestRateGiven == defaultInterestRate);
            assert(
                trustlineAgreement.interestRateReceived == defaultInterestRate
            );
        } else {
            assert(trustlineAgreement.interestRateGiven >= 0);
            assert(trustlineAgreement.interestRateReceived >= 0);
        }

        TrustlineAgreement storage storedTrustlineAgreement =
            trustlines[uniqueIdentifier(_a, _b)].agreement;
        if (_a < _b) {
            storedTrustlineAgreement.creditlineGiven = trustlineAgreement
                .creditlineGiven;
            storedTrustlineAgreement.creditlineReceived = trustlineAgreement
                .creditlineReceived;
            storedTrustlineAgreement.interestRateGiven = trustlineAgreement
                .interestRateGiven;
            storedTrustlineAgreement.interestRateReceived = trustlineAgreement
                .interestRateReceived;
            storedTrustlineAgreement.isFrozen = trustlineAgreement.isFrozen;
        } else {
            storedTrustlineAgreement.creditlineGiven = trustlineAgreement
                .creditlineReceived;
            storedTrustlineAgreement.creditlineReceived = trustlineAgreement
                .creditlineGiven;
            storedTrustlineAgreement.interestRateGiven = trustlineAgreement
                .interestRateReceived;
            storedTrustlineAgreement.interestRateReceived = trustlineAgreement
                .interestRateGiven;
            storedTrustlineAgreement.isFrozen = trustlineAgreement.isFrozen;
        }
    }

    // Provides the abstraction of whether a < b or b < a.
    function _storeTrustlineBalances(
        address _a,
        address _b,
        TrustlineBalances memory trustlineBalances
    ) internal {
        TrustlineBalances storage storedTrustlineBalance =
            trustlines[uniqueIdentifier(_a, _b)].balances;
        if (_a < _b) {
            storedTrustlineBalance.mtime = trustlineBalances.mtime;
            storedTrustlineBalance.balance = trustlineBalances.balance;
        } else {
            storedTrustlineBalance.mtime = trustlineBalances.mtime;
            storedTrustlineBalance.balance = -trustlineBalances.balance;
        }
    }

    function _loadTrustlineRequest(address _a, address _b)
        internal
        view
        returns (TrustlineRequest memory)
    {
        TrustlineRequest memory trustlineRequest =
            requestedTrustlineUpdates[uniqueIdentifier(_a, _b)];
        return trustlineRequest;
    }

    function _deleteTrustlineRequest(address _a, address _b) internal {
        delete requestedTrustlineUpdates[uniqueIdentifier(_a, _b)];
    }

    function _storeTrustlineRequest(
        address _a,
        address _b,
        TrustlineRequest memory _trustlineRequest
    ) internal {
        if (!customInterests) {
            assert(_trustlineRequest.interestRateGiven == defaultInterestRate);
            assert(
                _trustlineRequest.interestRateReceived == defaultInterestRate
            );
        } else {
            assert(_trustlineRequest.interestRateGiven >= 0);
            assert(_trustlineRequest.interestRateReceived >= 0);
        }

        TrustlineRequest storage trustlineRequest =
            requestedTrustlineUpdates[uniqueIdentifier(_a, _b)];

        trustlineRequest.creditlineGiven = _trustlineRequest.creditlineGiven;
        trustlineRequest.creditlineReceived = _trustlineRequest
            .creditlineReceived;
        trustlineRequest.interestRateGiven = _trustlineRequest
            .interestRateGiven;
        trustlineRequest.interestRateReceived = _trustlineRequest
            .interestRateReceived;
        trustlineRequest.initiator = _trustlineRequest.initiator;
        trustlineRequest.isFrozen = _trustlineRequest.isFrozen;
        trustlineRequest.transfer = _trustlineRequest.transfer;
    }

    // in this function, it is assumed _creditor is the initator of the trustline update (see _requestTrustlineUpdate())
    function _updateTrustline(
        address _creditor,
        address _debtor,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived,
        int16 _interestRateGiven,
        int16 _interestRateReceived,
        bool _isFrozen,
        int72 _transfer
    ) internal {
        require(
            !isNetworkFrozen,
            "The network is frozen and trustlines cannot be updated."
        );
        TrustlineAgreement memory trustlineAgreement =
            _loadTrustlineAgreement(_creditor, _debtor);
        if (_isTrustlineFrozen(trustlineAgreement)) {
            require(
                !_isFrozen,
                "Trustline is frozen, it cannot be updated unless unfrozen."
            );
        }
        require(
            customInterests ||
                (_interestRateGiven == defaultInterestRate &&
                    _interestRateReceived == defaultInterestRate),
            "Interest rates given and received must be equal to default interest rates."
        );
        if (customInterests) {
            require(
                _interestRateGiven >= 0 && _interestRateReceived >= 0,
                "Only positive interest rates are supported."
            );
            require(
                _interestRateGiven <= 2000 && _interestRateGiven >= -2000,
                "Interests rate given cannot exceed +-20%."
            );
            require(
                _interestRateReceived <= 2000 && _interestRateReceived >= -2000,
                "Interests rate received cannot exceed +-20%."
            );
        }

        // reduction of creditlines and interests given is always possible if trustline is not frozen
        if (
            _creditlineGiven <= trustlineAgreement.creditlineGiven &&
            _creditlineReceived <= trustlineAgreement.creditlineReceived &&
            _interestRateGiven <= trustlineAgreement.interestRateGiven &&
            _interestRateReceived == trustlineAgreement.interestRateReceived &&
            _isFrozen == trustlineAgreement.isFrozen &&
            !trustlineAgreement.isFrozen
        ) {
            // Prevent opening a trustline with 0 limits
            // as this would allow opening a trustline without counterparty's consent
            if (
                trustlineAgreement.creditlineGiven == 0 &&
                trustlineAgreement.creditlineReceived == 0 &&
                trustlineAgreement.interestRateGiven == 0 &&
                trustlineAgreement.interestRateReceived == 0 &&
                trustlineAgreement.isFrozen == false
            ) {
                revert("Can not open zero trustline.");
            }
            _deleteTrustlineRequest(_creditor, _debtor);
            _setTrustline(
                _creditor,
                _debtor,
                _creditlineGiven,
                _creditlineReceived,
                _interestRateGiven,
                _interestRateReceived,
                _isFrozen
            );
            return;
        }

        TrustlineRequest memory trustlineRequest =
            _loadTrustlineRequest(_creditor, _debtor);

        // if original initiator is debtor, try to accept request
        if (trustlineRequest.initiator == _debtor) {
            if (
                _creditlineReceived <= trustlineRequest.creditlineGiven &&
                _creditlineGiven <= trustlineRequest.creditlineReceived &&
                _interestRateGiven <= trustlineRequest.interestRateReceived &&
                _interestRateReceived == trustlineRequest.interestRateGiven &&
                _isFrozen == trustlineRequest.isFrozen &&
                _transfer == -trustlineRequest.transfer
            ) {
                _deleteTrustlineRequest(_creditor, _debtor);
                // _debtor and _creditor is switched because we want the initiator of the trustline to be _debtor.
                // So every Given / Received has to be switched.
                _setTrustline(
                    _debtor,
                    _creditor,
                    _creditlineReceived,
                    _creditlineGiven,
                    _interestRateReceived,
                    _interestRateGiven,
                    _isFrozen
                );

                if (_transfer > 0) {
                    _setBalance(_creditor, _debtor, -_transfer);
                    emit Transfer(
                        _creditor,
                        _debtor,
                        uint256(int256(_transfer)),
                        ""
                    );
                } else if (_transfer < 0) {
                    _setBalance(_debtor, _creditor, _transfer);
                    emit Transfer(
                        _debtor,
                        _creditor,
                        uint256(int256(-_transfer)),
                        ""
                    );
                }
            } else {
                _requestTrustlineUpdate(
                    _creditor,
                    _debtor,
                    _creditlineGiven,
                    _creditlineReceived,
                    _interestRateGiven,
                    _interestRateReceived,
                    _isFrozen,
                    _transfer
                );
            }
            // update the trustline request
        } else {
            _requestTrustlineUpdate(
                _creditor,
                _debtor,
                _creditlineGiven,
                _creditlineReceived,
                _interestRateGiven,
                _interestRateReceived,
                _isFrozen,
                _transfer
            );
        }
    }

    function _updateCreditlimits(
        address _creditor,
        address _debtor,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived
    ) internal {
        int16 interestRateGiven = defaultInterestRate;
        int16 interestRateReceived = defaultInterestRate;
        TrustlineAgreement memory trustlineAgreement =
            _loadTrustlineAgreement(_creditor, _debtor);
        bool isFrozen = trustlineAgreement.isFrozen;
        if (customInterests) {
            interestRateGiven = trustlineAgreement.interestRateGiven;
            interestRateReceived = trustlineAgreement.interestRateReceived;
        }
        _updateTrustline(
            _creditor,
            _debtor,
            _creditlineGiven,
            _creditlineReceived,
            interestRateGiven,
            interestRateReceived,
            isFrozen,
            0
        );
    }

    // Actually change the trustline
    function _setTrustline(
        address _creditor,
        address _debtor,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived,
        int16 _interestRateGiven,
        int16 _interestRateReceived,
        bool _isFrozen
    ) internal virtual {
        Trustline memory _trustline = _loadTrustline(_creditor, _debtor);

        // Because the interest rate might change, we need to apply interests.
        if (
            (_interestRateGiven != _trustline.agreement.interestRateGiven ||
                _interestRateReceived !=
                _trustline.agreement.interestRateReceived) &&
            _trustline.balances.balance != 0
        ) {
            _applyInterests(_trustline);
            emit BalanceUpdate(_creditor, _debtor, _trustline.balances.balance);
        }

        addToUsersAndFriends(_creditor, _debtor);
        _trustline.agreement.creditlineGiven = _creditlineGiven;
        _trustline.agreement.creditlineReceived = _creditlineReceived;
        _trustline.agreement.interestRateGiven = _interestRateGiven;
        _trustline.agreement.interestRateReceived = _interestRateReceived;
        _trustline.agreement.isFrozen = _isFrozen;
        _storeTrustlineBalances(_creditor, _debtor, _trustline.balances);
        _storeTrustlineAgreement(_creditor, _debtor, _trustline.agreement);

        emit TrustlineUpdate(
            _creditor,
            _debtor,
            _creditlineGiven,
            _creditlineReceived,
            _interestRateGiven,
            _interestRateReceived,
            _isFrozen
        );
    }

    function _setBalance(
        address _creditor,
        address _debtor,
        int72 _balance
    ) internal {
        TrustlineBalances memory trustlineBalances;
        trustlineBalances.balance = _balance;
        trustlineBalances.mtime = uint32(block.timestamp);
        _storeTrustlineBalances(_creditor, _debtor, trustlineBalances);
        emit BalanceUpdate(_creditor, _debtor, _balance);
    }

    function _requestTrustlineUpdate(
        address _creditor,
        address _debtor,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived,
        int16 _interestRateGiven,
        int16 _interestRateReceived,
        bool _isFrozen,
        int72 _transfer
    ) internal {
        _storeTrustlineRequest(
            _creditor,
            _debtor,
            TrustlineRequest(
                _creditlineGiven,
                _creditlineReceived,
                _interestRateGiven,
                _interestRateReceived,
                _isFrozen,
                _creditor,
                _transfer
            )
        );

        emit TrustlineUpdateRequest(
            _creditor,
            _debtor,
            _creditlineGiven,
            _creditlineReceived,
            _interestRateGiven,
            _interestRateReceived,
            _isFrozen,
            _transfer
        );
    }

    function _calculateFees(
        uint64 _imbalanceGenerated,
        uint16 _capacityImbalanceFeeDivisor
    ) internal pure returns (uint64) {
        if (_capacityImbalanceFeeDivisor == 0 || _imbalanceGenerated == 0) {
            return 0;
        }
        // Calculate the fees with c * imbalance = imbalance / divisor
        // We round up by using (imbalance - 1) / divisor + 1
        return (_imbalanceGenerated - 1) / _capacityImbalanceFeeDivisor + 1;
    }

    function _calculateFeesReverse(
        uint64 _imbalanceGenerated,
        uint16 _capacityImbalanceFeeDivisor
    ) internal pure returns (uint64) {
        if (_capacityImbalanceFeeDivisor == 0 || _imbalanceGenerated == 0) {
            return 0;
        }
        // Calculate the fees in reverse with c * imbalance / (1 - c) = imbalance / (divisor - 1)
        // We round up using (imbalance - 1) / (divisor - 1) + 1
        return
            (_imbalanceGenerated - 1) / (_capacityImbalanceFeeDivisor - 1) + 1;
    }

    function _calculateImbalanceGenerated(uint64 _value, int72 _balance)
        internal
        pure
        returns (uint64)
    {
        int72 imbalanceGenerated = _value;
        if (_balance > 0) {
            imbalanceGenerated = _value - _balance;
            // Overflow
            if (imbalanceGenerated > _value) {
                return 0;
            }
        }
        if (imbalanceGenerated <= 0) {
            return 0;
        }
        uint64 result = uint64(uint72(imbalanceGenerated));
        require(
            result == imbalanceGenerated,
            "The imbalance does not fit into uint64."
        );
        return result;
    }

    // Calculates a representation of how happy or unhappy a participant is because of the interests after a transfer
    // The higher the value returned, the higher the happiness of the sender and the higher the unhappiness of the receiver
    // This is called after the transfer has been done, so _trustline is the trustline from the senders view after the transfer
    // has been done. _balanceBefore is the sender's balance before the transfer has been done.
    function _interestHappiness(
        Trustline memory _trustline,
        int72 _balanceBefore
    ) internal pure returns (int256) {
        int72 _balance = _trustline.balances.balance;
        int256 transferredValue = int256(_balanceBefore) - _balance;

        if (_balanceBefore <= 0) {
            // Sender already owes receiver, this will only effect the interest rate received
            return
                -transferredValue * _trustline.agreement.interestRateReceived;
        } else if (_balance >= 0) {
            // Receiver owes sender before and after the transfer. This only effects the interest rate received
            return -transferredValue * _trustline.agreement.interestRateGiven;
        } else {
            // It effects both interest rates
            // Before the transfer: Receiver owes to sender balanceBefore;
            // After the transfer: Sender owes to receiver balance;
            return
                -int256(_balanceBefore) *
                _trustline.agreement.interestRateGiven +
                int256(_balance) *
                _trustline.agreement.interestRateReceived;
        }
    }

    // Returns whether a trustline is frozen
    // Should be more gas efficient than public isTrustlineFrozen() if agreement already loaded in memory
    function _isTrustlineFrozen(TrustlineAgreement memory agreement)
        internal
        view
        returns (bool)
    {
        if (isNetworkFrozen) {
            return true;
        }
        return agreement.isFrozen;
    }

    function uniqueIdentifier(address _a, address _b)
        internal
        pure
        virtual
        returns (bytes32)
    {
        require(_a != _b, "Unique identifiers require different addresses");
        if (_a < _b) {
            return keccak256(abi.encodePacked(_a, _b));
        } else if (_a > _b) {
            return keccak256(abi.encodePacked(_b, _a));
        } else {
            revert("Unreachable code.");
        }
    }
}

// SPDX-License-Identifier: MIT
