pragma solidity ^0.5.8;


import "./lib/it_set_lib.sol";
import "./tokens/Receiver_Interface.sol";
import "./lib/Ownable.sol";
import "./lib/Destructable.sol";
import "./lib/Authorizable.sol";
import "./lib/ERC165.sol";
import "./CurrencyNetworkInterface.sol";
import "./debtTrackingInterface.sol";


/**
 * CurrencyNetwork
 *
 * Main contract of Trustlines, encapsulates all trustlines of one currency network.
 * Implements functions to ripple payments in a currency network. Implements core features of ERC20
 *
 **/
contract CurrencyNetwork is CurrencyNetworkInterface, Ownable, Authorizable, Destructable, debtTrackingInterface, ERC165 {

    // Constants
    int72 constant MAX_BALANCE = 2**71 - 1;
    int72 constant MIN_BALANCE = - MAX_BALANCE; // for symmetry MIN_BALANCE needs to be the same absolute value like MAX_BALANCE
    int256 constant SECONDS_PER_YEAR = 60*60*24*365;

    using ItSet for ItSet.AddressSet;
    mapping (bytes32 => Trustline) internal trustlines;
    // mapping uniqueId => trustline request
    mapping (bytes32 => TrustlineRequest) internal requestedTrustlineUpdates;

    // friends, users address has a trustline with
    mapping (address => ItSet.AddressSet) internal friends;
    // list of all users of the system
    ItSet.AddressSet internal users;
    // mapping of a pair of user to the signed debt in the point of view of the lowest address
    mapping (bytes32 => int72) public debt;
    // map each user to its onboarder
    mapping (address => address) public onboarder;
    // value in the mapping for users that do not have an onboarder
    address constant NO_ONBOARDER = address(1);

    // meta data for token part
    string public name;
    string public symbol;
    uint8 public decimals;

    bool public isInitialized;
    uint public expirationTime;
    bool public isNetworkFrozen;

    // Divides current value being transferred to calculate the capacity fee which equals the imbalance fee
    uint16 public capacityImbalanceFeeDivisor;

    // interests settings, interests are expressed in 0.01% per year
    int16 public defaultInterestRate;
    bool public customInterests;
    bool public preventMediatorInterests;

    // Events
    event Transfer(address indexed _from, address indexed _to, uint _value, bytes _extraData);

    event TrustlineUpdateRequest(
        address indexed _creditor,
        address indexed _debtor,
        uint _creditlineGiven,
        uint _creditlineReceived,
        int _interestRateGiven,
        int _interestRateReceived,
        bool _isFrozen
    );

    event TrustlineUpdate(
        address indexed _creditor,
        address indexed _debtor,
        uint _creditlineGiven,
        uint _creditlineReceived,
        int _interestRateGiven,
        int _interestRateReceived,
        bool _isFrozen
    );

    event BalanceUpdate(address indexed _from, address indexed _to, int256 _value);

    event Onboard(address indexed _onboarder, address indexed _onboardee);

    event DebtUpdate(address _debtor, address _creditor, int72 _newDebt);

    event NetworkFreeze();

    // for accounting balance and trustline agreement between two users introducing fees and interests
    // currently uses 160 + 136 bits, 216 remaining to make two structs
    struct Trustline {
        // A < B (A is the lower address)
        TrustlineAgreement agreement;
        TrustlineBalances balances;
    }

    struct TrustlineAgreement {

        uint64 creditlineGiven;       //  creditline given by A to B, always positive
        uint64 creditlineReceived;    //  creditline given by B to A, always positive

        int16 interestRateGiven;      //  interest rate set by A for creditline given by A to B in 0.01% per year
        int16 interestRateReceived;   //  interest rate set by B for creditline given from B to A in 0.01% per year

        bool isFrozen;                //  8 bits
        int88 padding;                //  fill up to 256bit
    }

    struct TrustlineBalances {

        uint16 feesOutstandingA;       //  fees outstanding by A
        uint16 feesOutstandingB;       //  fees outstanding by B

        uint32 mtime;                  //  last time interests were applied

        int72 balance;                 //  balance between A and B, balance is >0 if B owes A, negative otherwise.
                                       //  balance(B,A) = - balance(A,B)
        int120 padding;                //  fill up to 256 bit
    }

    struct TrustlineRequest {
        uint64 creditlineGiven;
        uint64 creditlineReceived;
        int16 interestRateGiven;
        int16 interestRateReceived;
        bool isFrozen;
        address initiator;
    }

    constructor() public {
        // solium-disable-previous-line no-empty-blocks
        // don't do anything here due to upgradeability issues (no constructor-call on replacement).
    }

    function() external {}

    /**
     * @notice Initialize the currency Network
     * @param _name The name of the currency
     * @param _symbol The symbol of the currency
     * @param _decimals Number of decimals of the currency
     * @param _capacityImbalanceFeeDivisor Divisor of the imbalance fee. The fee is 1 / _capacityImbalanceFeeDivisor
     * @param _defaultInterestRate The default interests for every trustlines in 0.001% per year
     * @param _customInterests Flag to allow or disallow trustlines to have custom interests
     * @param _preventMediatorInterests Flag to allow or disallow transactions resulting in loss of interests for
     *         intermediaries, unless the transaction exclusively reduces balances
     * @param _expirationTime Time after which the currency network is frozen and cannot be used anymore. Setting
     *         this value to zero disables freezing.
     */
    function init(
        string calldata _name,
        string calldata _symbol,
        uint8 _decimals,
        uint16 _capacityImbalanceFeeDivisor,
        int16 _defaultInterestRate,
        bool _customInterests,
        bool _preventMediatorInterests,
        uint _expirationTime
    )
        external
        onlyOwner
    {
        require(!isInitialized, "Currency Network already initialized.");
        isInitialized = true;

        // verifies that only one parameter is selected.
        require(
            ! ((_defaultInterestRate != 0) && _customInterests),
            "Custom interests are set; default interest rate must be zero."
        );
        require(
            !_preventMediatorInterests || (_preventMediatorInterests && _customInterests),
            "Prevent mediator interest cannot be set without using custom interests."
        );

        require(
            _expirationTime == 0 || _expirationTime > now,
            "Expiration time must be either in the future or zero to disable it."
        );

        name = _name;
        symbol = _symbol;
        decimals = _decimals;
        capacityImbalanceFeeDivisor = _capacityImbalanceFeeDivisor;
        defaultInterestRate = _defaultInterestRate;
        customInterests = _customInterests;
        preventMediatorInterests = _preventMediatorInterests;
        expirationTime = _expirationTime;

        onboarder[owner] = NO_ONBOARDER;
    }

    /**
     * @notice send `_value` token to `_to` from `msg.sender`
     * The fees will be payed by the sender, so `_value` is the amount received by `_to`
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @param _maxFee Maximum fee the sender wants to pay
     * @param _path Path between msg.sender and _to
     * @param _extraData extra data bytes to be logged in the Transfer event
     **/
    function transfer(
        address _to,
        uint64 _value,
        uint64 _maxFee,
        address[] calldata _path,
        bytes calldata _extraData
    )
        external
        returns (bool _success)
    {
        _success = _mediatedTransferSenderPays(
            msg.sender,
            _to,
            _value,
            _maxFee,
            _path);

        if (_success) {
            emit Transfer(
                msg.sender,
                _to,
                _value,
                _extraData
            );
        }
    }

    /**
     * @notice send `_value` token to `_to` from `_from`
     * msg.sender needs to be authorized to call this function
     * @param _from The address of the sender
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @param _maxFee Maximum fee the sender wants to pay
     * @param _path Path between _from and _to
     * @param _extraData extra data bytes to be logged in the Transfer event
     **/
    function transferFrom(
        address _from,
        address _to,
        uint64 _value,
        uint64 _maxFee,
        address[] calldata _path,
        bytes calldata _extraData
    )
        external
        returns (bool success)
    {
        require(authorized[msg.sender], "The sender of the message is not authorized.");

        success = _mediatedTransferSenderPays(
            _from,
            _to,
            _value,
            _maxFee,
            _path);

        if (success) {
            emit Transfer(
                _from,
                _to,
                _value,
                _extraData
            );
        }
    }

    /**
     * @notice send `_value` token to `_to` from `_from`
     * `_from` needs to have a debt towards `_to` of at least `_value`
     * `_to` needs to be msg.sender
     * @param _from The address of the sender
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @param _maxFee Maximum fee the receiver wants to pay
     * @param _path Path between _from and _to
     * @param _extraData extra data bytes to be logged in the Transfer event
     **/
    function debitTransfer(
        address _from,
        address _to,
        uint64 _value,
        uint64 _maxFee,
        address[] calldata _path,
        bytes calldata _extraData
    )
        external returns (bool success)
    {
        require(_to == msg.sender, "The transfer can only be initiated by the creditor (_to).");
        require(getDebt(_from, _to) >= _value, "The sender does not have such debt towards the receiver.");
        _reduceDebt(_from, _to, _value);

        success = _mediatedTransferReceiverPays(
            _from,
            _to,
            _value,
            _maxFee,
            _path);

        if (success) {
            emit Transfer(
                _from,
                _to,
                _value,
                _extraData
            );
        } else {
            revert("Transfer failed.");
        }
    }

    /**
     * @notice send `_value` token to `_to` from `msg.sender`
     * The fees will be payed by the receiver, so `_value` is the amount that is sent out by `msg.sender`
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @param _maxFee Maximum fee the sender wants to pay
     * @param _path Path between msg.sender and _to
     * @param _extraData extra data bytes to be logged in the Transfer event
     **/
    function transferReceiverPays(
        address _to,
        uint64 _value,
        uint64 _maxFee,
        address[] calldata _path,
        bytes calldata _extraData
    )
        external
        returns (bool _success)
    {
        _success = _mediatedTransferReceiverPays(
            msg.sender,
            _to,
            _value,
            _maxFee,
            _path);

        if (_success) {
            emit Transfer(
                msg.sender,
                _to,
                _value,
                _extraData
            );
        }
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
     * @return true, if the credit was successful
     */
    function updateTrustline(
        address _debtor,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived,
        int16 _interestRateGiven,
        int16 _interestRateReceived,
        bool _isFrozen
    )
        external
        returns (bool _success)
    {

        address _creditor = msg.sender;

        return _updateTrustline(
            _creditor,
            _debtor,
            _creditlineGiven,
            _creditlineReceived,
            _interestRateGiven,
            _interestRateReceived,
            _isFrozen
        );
    }

    /**
     * @notice `msg.sender` offers a trustline update to `_debtor` of `_creditlineGiven` tokens for `_creditlineReceived`
     * token
     * Needs to be accepted by the other party, unless we reduce both values.
     * @param _debtor The other party of the trustline agreement
     * @param _creditlineGiven The creditline limit given by msg.sender
     * @param _creditlineReceived The creditline limit given _debtor
     * @return true, if the credit was successful
     */
    function updateCreditlimits(
        address _debtor,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived
    )
        external
        returns (bool _success)
    {
        address _creditor = msg.sender;

        return _updateCreditlimits(
            _creditor,
            _debtor,
            _creditlineGiven,
            _creditlineReceived
        );
    }

    /**
     * @notice `msg.sender` offers a trustline update to `_debtor` of `_creditlineGiven` tokens for `_creditlineReceived`
     * token with default interests
     * Needs to be accepted by the other party, unless we reduce both values.
     * @param _debtor The other party of the trustline agreement
     * @param _creditlineGiven The creditline limit given by msg.sender
     * @param _creditlineReceived The creditline limit given _debtor
     * @param _isFrozen Whether the initiator asks for freezing the trustline
     * @return true, if the credit was successful
     */
    function updateTrustlineDefaultInterests(
        address _debtor,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived,
        bool _isFrozen
    )
        external
        returns (bool _success)
    {
        address _creditor = msg.sender;

        return _updateTrustline(
            _creditor,
            _debtor,
            _creditlineGiven,
            _creditlineReceived,
            defaultInterestRate,
            defaultInterestRate,
            _isFrozen
        );
    }

    /**
     * @notice `msg.sender` closes a trustline with `_otherParty`
     * For this to succeed the balance of this trustline needs to be zero
     * @param _otherParty The other party of the trustline agreement
     * @return true, if the trustline was closed
     */
    function closeTrustline(
        address _otherParty
    )
        external
        returns (bool _success)
    {

        address from = msg.sender;

        _closeTrustline(
            from,
            _otherParty
        );

        return true;
    }

    /** @notice Close the trustline between `msg.sender` and `_otherParty` by doing a triangular transfer over `_path
        @param _otherParty Address of the other party to close the trustline with
        @param _maxFee maximum fees the sender is willing to pay
        @param _path The path along, which to do the triangulation
     */
    function closeTrustlineByTriangularTransfer(
        address _otherParty,
        uint32 _maxFee,
        address[] calldata _path
    )
        external
    {
        _closeTrustlineByTriangularTransfer(
            msg.sender,
            _otherParty,
            _maxFee,
            _path);
    }

    /**
     * @notice Used to increase the debt tracked by the currency network of msg.sender towards creditor address
     * @param creditor The address towards which msg.sender increases its debt
     * @param value The value to increase the debt by
     */
    function increaseDebt(address creditor, uint64 value) external {
        _addToDebt(msg.sender, creditor, value);
    }

    /**
     * @dev The ERC20 Token balance for the spender. This is different from the balance within a trustline.
     *      In Trustlines this is the spendable amount
     * @param _owner The address from which the balance will be retrieved
     * @return The balance
     */
    function balanceOf(address _owner) external view returns (uint256) {
        return spendable(_owner);
    }

    /**
     * @return total amount of tokens. In Trustlines this is the sum of all creditlines
     */
    function totalSupply() external view returns (uint256 supply) {
        supply = 0;
        address[] storage userList = users.list;
        for (uint i = 0; i < userList.length; i++) {
            supply += spendable(userList[i]);
        }
    }

    /**
    * Query the trustline between two users.
    * Can be removed once structs are supported in the ABI
    */
    function getAccount(address _a, address _b) external view returns (int, int, int, int, bool, int, int, int, int) {
        Trustline memory trustline = _loadTrustline(_a, _b);

        return (
            trustline.agreement.creditlineGiven,
            trustline.agreement.creditlineReceived,
            trustline.agreement.interestRateGiven,
            trustline.agreement.interestRateReceived,
            trustline.agreement.isFrozen || isNetworkFrozen,
            trustline.balances.feesOutstandingA,
            trustline.balances.feesOutstandingB,
            trustline.balances.mtime,
            trustline.balances.balance);
    }

    function freezeNetwork() external {
        require(expirationTime != 0, "The currency network has disabled freezing.");
        require(expirationTime <= now, "The currency network cannot be frozen yet.");
        isNetworkFrozen = true;
        emit NetworkFreeze();
    }

    function supportsInterface(
        bytes4 interfaceID
    )
        external
        view
        returns (bool)
    {
        return (
            interfaceID == this.supportsInterface.selector || // ERC165
            (   // This needs to be in sync with CurrencyNetworkInterface.sol
                interfaceID == (
                    this.name.selector ^
                    this.symbol.selector ^
                    this.decimals.selector ^
                    this.transfer.selector ^
                    this.transferFrom.selector ^
                    this.balance.selector ^
                    this.creditline.selector
                )
            )
        );
    }

    /**
     * @notice Checks for the spendable amount by spender
     * @param _spender The address from which the balance will be retrieved
     * @return spendable The spendable amount
     */
    function spendable(address _spender) public view returns (uint _spendable) {
        _spendable = 0;
        address[] storage myfriends = friends[_spender].list;
        for (uint i = 0; i < myfriends.length; i++) {
            _spendable += spendableTo(_spender, myfriends[i]);
        }
    }

    /**
     * @notice the maximum spendable amount by the spender to the receiver.
     * @param _spender The account spending the tokens
     * @param _receiver the receiver that receives the tokens
     * @return Amount of remaining tokens allowed to spend
     */
    function spendableTo(address _spender, address _receiver) public view returns (uint remaining) {
        Trustline memory trustline = _loadTrustline(_spender, _receiver);
        if (_isTrustlineFrozen(trustline.agreement)) {
            return 0;
        }
        int72 balance = trustline.balances.balance;
        uint64 creditline = trustline.agreement.creditlineReceived;
        remaining = uint(creditline + balance);
    }

    /**
     * @notice The creditline limit given by `_creditor` to `_debtor`
     * @return Amount tokens allowed to spent
     */
    function creditline(address _creditor, address _debtor) public view returns (uint _creditline) {
        // returns the current creditline given by A to B
        TrustlineAgreement memory trustlineAgreement = _loadTrustlineAgreement(_creditor, _debtor);
        _creditline = trustlineAgreement.creditlineGiven;
    }

    /**
     * @notice The interest rate given by `_creditor` to `_debtor`
     * @return Interest rate on the balance of the line
     */
    function interestRate(address _creditor, address _debtor) public view returns (int16 _interestRate) {
        // returns the current interests given by A to B
        TrustlineAgreement memory trustlineAgreement = _loadTrustlineAgreement(_creditor, _debtor);
        _interestRate = trustlineAgreement.interestRateGiven;
    }

    /*
     * @notice returns what B owes to A
     */
    function balance(address _a, address _b) public view returns (int _balance) {
        TrustlineBalances memory trustlineBalances = _loadTrustlineBalances(_a, _b);
        _balance = trustlineBalances.balance;
    }

    function getFriends(address _user) public view returns (address[] memory) {
        return friends[_user].list;
    }

    function getUsers() public view returns (address[] memory) {
        return users.list;
    }

    function isTrustlineFrozen(address a, address b) public view returns (bool) {
        if (isNetworkFrozen) {
            return true;
        }
        TrustlineAgreement memory trustlineAgreement = _loadTrustlineAgreement(a, b);
        return trustlineAgreement.isFrozen;
    }

    /**
     * @notice Get the debt owed by debtor to creditor, may be negative if creditor owes debtor
     * @param debtor The address of which we query the debt
     * @param creditor The address towards which the debtor owes money
     * @return the debt of the debtor to the creditor, equal to the opposite of the debt of the creditor to the debtor
     */
    function getDebt(address debtor, address creditor) public view returns (int256) {
        if (debtor < creditor) {
            return debt[uniqueIdentifier(debtor, creditor)];
        } else {
            return - debt[uniqueIdentifier(debtor, creditor)];
        }
    }

    // This function transfers value over this trustline
    // For that it modifies the value of the balance stored in the trustline for sender and receiver
    function _applyDirectTransfer(
        Trustline memory _trustline,
        uint64 _value
    )
        internal
        pure
    {
        int72 newBalance = _trustline.balances.balance - _value;
        require(
            newBalance <= _trustline.balances.balance,
            "The transferred value underflows the balance"
        );

        // check if creditline is not exceeded
        uint64 creditlineReceived = _trustline.agreement.creditlineReceived;
        require(
            -newBalance <= int72(creditlineReceived),
            "The transferred value exceeds the capacity of the credit line."
        );

        _trustline.balances.balance = newBalance;
    }

    function _applyInterests(
        Trustline memory _trustline
    )
        internal
        view
    {
        _trustline.balances.balance = _calculateBalanceWithInterests(
            _trustline.balances.balance,
            _trustline.balances.mtime,
            now,
            _trustline.agreement.interestRateGiven,
            _trustline.agreement.interestRateReceived
        );
        _trustline.balances.mtime = uint32(now);
    }

    function _mediatedTransferSenderPays(
        address _from,
        address _to,
        uint64 _value,
        uint64 _maxFee,
        address[] memory _path
    )
        internal
        returns (bool)
    {
        require(_path.length > 0, "No path was given.");
        require(_to == _path[_path.length - 1], "The last address of the path does not match the 'to' address.");

        uint64 forwardedValue = _value;
        uint64 fees = 0;
        int receiverUnhappiness = 0;
        int receiverHappiness = 0;
        bool reducingDebtOfNextHopOnly = true;

        // check path in reverse to correctly accumulate the fee
        for (uint i = _path.length; i > 0; i--) {
            // the address of the receiver is _path[i-1]
            address sender;
            uint64 fee;
            if (i == 1) {
                sender = _from;
            } else {
                sender = _path[i-2];
            }
            // Load trustline only once at the beginning
            Trustline memory trustline = _loadTrustline(sender, _path[i-1]);
            require(! _isTrustlineFrozen(trustline.agreement), "The path given is incorrect: one trustline in the path is frozen.");
            _applyInterests(trustline);

            if (i == _path.length) {
                fee = 0; // receiver should not get a fee
            } else {
                fee = _calculateFeesReverse(_imbalanceGenerated(forwardedValue, trustline.balances.balance), capacityImbalanceFeeDivisor);
            }

            // forward the value + the fee
            forwardedValue += fee;
            //Overflow check
            require(forwardedValue >= fee, "The fees overflow the value to be forwarded.");
            fees += fee;
            require(fees <= _maxFee, "The fees exceed the max fee parameter.");


            int72 balanceBefore = trustline.balances.balance;

            _applyDirectTransfer(
                trustline,
                forwardedValue);


            if (preventMediatorInterests) {
                // prevent intermediaries from paying more interests than they receive
                // unless the transaction helps in reducing the debt of the next hop in the path
                receiverHappiness = receiverUnhappiness;  // receiver was the sender in last iteration
                receiverUnhappiness = _interestHappiness(trustline, balanceBefore);
                require(
                    receiverUnhappiness <= receiverHappiness || reducingDebtOfNextHopOnly,
                    "The transfer was prevented by the prevent mediator interests strategy"
                );
                reducingDebtOfNextHopOnly = trustline.balances.balance >= 0;
            }

            // store only balance because trustline agreement did not change
            _storeTrustlineBalances(sender, _path[i-1], trustline.balances);
            // The BalanceUpdate always has to be in the transfer direction
            emit BalanceUpdate(sender, _path[i-1], trustline.balances.balance);
        }

        return true;
    }

    /* like _mediatedTransfer only the receiver pays
       which means we start walking the _path at the sender and substract fees from the forwarded value
    */
    function _mediatedTransferReceiverPays(
        address _from,
        address _to,
        uint64 _value,
        uint64 _maxFee,
        address[] memory _path
    )
        internal
        returns (bool)
    {
        require(_path.length > 0, "No path was given.");
        require(_to == _path[_path.length - 1], "The last address of the path does not match the 'to' address.");

        uint64 forwardedValue = _value;
        uint64 fees = 0;
        int senderHappiness = - 2**255;
        int senderUnhappiness = - 2**255;
        bool reducingDebtOnly = true;

        // check path starting from sender correctly accumulate the fee
        for (uint i = 0; i < _path.length; i++) {
            // the address of the receiver is _path[i]
            address sender;
            uint64 fee;
            if (i == 0) {
                sender = _from;
            } else {
                sender = _path[i-1];
            }
            // Load trustline only once at the beginning
            Trustline memory trustline = _loadTrustline(sender, _path[i]);
            require(! _isTrustlineFrozen(trustline.agreement), "The path given is incorrect: one trustline in the path is frozen.");
            _applyInterests(trustline);

            int72 balanceBefore = trustline.balances.balance;

            _applyDirectTransfer(
                trustline,
                forwardedValue);

            if (preventMediatorInterests) {
                // prevent intermediaries from paying more interests than they receive
                // unless the transaction helps in reducing the debt of the next hop in the path
                senderUnhappiness = senderHappiness;  // sender was the receiver in last iteration
                senderHappiness = _interestHappiness(trustline, balanceBefore);
                reducingDebtOnly = trustline.balances.balance >= 0;
                require(
                    senderHappiness >= senderUnhappiness || reducingDebtOnly,
                    "The transfer was prevented by the prevent mediator interests strategy"
                );
            }

            // store only balance because trustline agreement did not change
            _storeTrustlineBalances(sender, _path[i], trustline.balances);
            // The BalanceUpdate always has to be in the transfer direction
            emit BalanceUpdate(sender, _path[i], trustline.balances.balance);

            if (i == _path.length - 1) {
                break; // receiver is not a mediator, so no fees
            }

            // calculate fees for next mediator
            fee = _calculateFees(_imbalanceGenerated(forwardedValue, balanceBefore), capacityImbalanceFeeDivisor);
            // Underflow check
            require(forwardedValue > fee, "The fees underflow the value to be forwarded.");
            forwardedValue -= fee;

            fees += fee;
            require(fees <= _maxFee, "The fees exceed the max fee parameter.");

        }

        return true;
    }

    /* close a trustline, which must have a balance of zero */
    function _closeTrustline(
        address _from,
        address _otherParty)
        internal
    {
        TrustlineBalances memory balances = _loadTrustlineBalances(_from, _otherParty);
        require(balances.balance == 0, "A trustline can only be closed if its balance is zero.");
        require(!isTrustlineFrozen(_from, _otherParty), "The trustline is frozen and cannot be closed.");

        bytes32 uniqueId = uniqueIdentifier(_from, _otherParty);
        delete requestedTrustlineUpdates[uniqueId];
        delete trustlines[uniqueId];
        friends[_from].remove(_otherParty);
        friends[_otherParty].remove(_from);
        emit TrustlineUpdate(
            _from,
            _otherParty,
            0,
            0,
            0,
            0,
            false);
    }

    /* close a trustline by doing a triangular transfer

       this function receives the path along which to do the transfer. This path
       is computed by the relay server based on the then current state of the
       balance. In case the balance changed it's sign, the path will not have
       the right 'shape' and the require statements below will revert the
       transaction.

       XXX This function is currently broken for balances which do not fit into
       a uint32. We may repair that later when merging the interest changes.
     */
    function _closeTrustlineByTriangularTransfer(
        address _from,
        address _otherParty,
        uint32 _maxFee,
        address[] memory _path)
        internal
    {
        Trustline memory trustline = _loadTrustline(_from, _otherParty);
        require(!_isTrustlineFrozen(trustline.agreement), "The trustline is frozen and cannot be closed.");
        _applyInterests(trustline);
        /* we could as well call _storeTrustlineBalances here. It doesn't matter for the
           _mediatedTransfer/_mediatedTransferReceiverPays calls below since the
           interest will be recomputed if we don't call storeTrustlineBalances here. We
           may investigate what's cheaper gas-wise later.
        */
        TrustlineBalances memory balances = trustline.balances;
        if (balances.balance > 0) {
            require(
                _path.length >= 2,
                "The path given is too short to be correct."
            );
            require(
                _from == _path[_path.length - 1],
                "The last element of the path does not match with the _from address."
            );
            require(
                _path[0] == _otherParty,
                "The first element of the path does not match with the _otherParty address."
            );
            _mediatedTransferReceiverPays(
                _from,
                _from,
                uint32(balances.balance),
                _maxFee,
                _path
            );
        } else if (balances.balance < 0) {
            require(
                _path.length >= 2,
                "The path given is too short to be correct."
            );
            require(
                _from == _path[_path.length - 1],
                "The last element of the path does not match with the _from address"
            );
            require(
                _path[_path.length - 2] == _otherParty,
                "The second to last element of the path has to be _otherParty address."
            );
            _mediatedTransferSenderPays(
                _from,
                _from,
                uint32(-balances.balance),
                _maxFee,
                _path
            );
        } // else {} /* balance is zero, there's nothing to do here */

        _closeTrustline(_from, _otherParty);
    }

    function addToUsersAndFriends(address _a, address _b) internal {
        users.insert(_a);
        users.insert(_b);
        friends[_a].insert(_b);
        friends[_b].insert(_a);
    }

    function _loadTrustline(address _a, address _b) internal view returns (Trustline memory) {
        Trustline memory trustline;
        trustline.agreement = _loadTrustlineAgreement(_a, _b);
        trustline.balances = _loadTrustlineBalances(_a, _b);
        return trustline;
    }

    function _loadTrustlineAgreement(address _a, address _b) internal view returns (TrustlineAgreement memory) {
        TrustlineAgreement memory trustlineAgreement = trustlines[uniqueIdentifier(_a, _b)].agreement;
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

    function _loadTrustlineBalances(address _a, address _b) internal view returns (TrustlineBalances memory) {
        TrustlineBalances memory balances = trustlines[uniqueIdentifier(_a, _b)].balances;
        TrustlineBalances memory result;
        if (_a < _b) {
            result = balances;
        } else {
            result.feesOutstandingB = balances.feesOutstandingA;
            result.feesOutstandingA = balances.feesOutstandingB;
            result.mtime = balances.mtime;
            result.balance = - balances.balance;
        }
        return result;
    }

    // Provides the abstraction of whether a < b or b < a.
    function _storeTrustlineAgreement(address _a, address _b, TrustlineAgreement memory trustlineAgreement) internal {
        if (!customInterests) {
            assert(trustlineAgreement.interestRateGiven == defaultInterestRate);
            assert(trustlineAgreement.interestRateReceived == defaultInterestRate);
        } else {
            assert(trustlineAgreement.interestRateGiven >= 0);
            assert(trustlineAgreement.interestRateReceived >= 0);
        }

        TrustlineAgreement storage storedTrustlineAgreement = trustlines[uniqueIdentifier(_a, _b)].agreement;
        if (_a < _b) {
            storedTrustlineAgreement.creditlineGiven = trustlineAgreement.creditlineGiven;
            storedTrustlineAgreement.creditlineReceived = trustlineAgreement.creditlineReceived;
            storedTrustlineAgreement.interestRateGiven = trustlineAgreement.interestRateGiven;
            storedTrustlineAgreement.interestRateReceived = trustlineAgreement.interestRateReceived;
            storedTrustlineAgreement.isFrozen = trustlineAgreement.isFrozen;
            storedTrustlineAgreement.padding = trustlineAgreement.padding;
        } else {
            storedTrustlineAgreement.creditlineGiven = trustlineAgreement.creditlineReceived;
            storedTrustlineAgreement.creditlineReceived = trustlineAgreement.creditlineGiven;
            storedTrustlineAgreement.interestRateGiven = trustlineAgreement.interestRateReceived;
            storedTrustlineAgreement.interestRateReceived = trustlineAgreement.interestRateGiven;
            storedTrustlineAgreement.isFrozen = trustlineAgreement.isFrozen;
            storedTrustlineAgreement.padding = trustlineAgreement.padding;
        }
    }

    // Provides the abstraction of whether a < b or b < a.
    function _storeTrustlineBalances(address _a, address _b, TrustlineBalances memory trustlineBalances) internal {
        TrustlineBalances storage storedTrustlineBalance = trustlines[uniqueIdentifier(_a, _b)].balances;
        if (_a < _b) {
            storedTrustlineBalance.feesOutstandingA = trustlineBalances.feesOutstandingA;
            storedTrustlineBalance.feesOutstandingB = trustlineBalances.feesOutstandingB;
            storedTrustlineBalance.mtime = trustlineBalances.mtime;
            storedTrustlineBalance.balance = trustlineBalances.balance;
            storedTrustlineBalance.padding = trustlineBalances.padding;
        } else {
            storedTrustlineBalance.feesOutstandingA = trustlineBalances.feesOutstandingB;
            storedTrustlineBalance.feesOutstandingB = trustlineBalances.feesOutstandingA;
            storedTrustlineBalance.mtime = trustlineBalances.mtime;
            storedTrustlineBalance.balance = - trustlineBalances.balance;
            storedTrustlineBalance.padding = trustlineBalances.padding;
        }
    }

    function _loadTrustlineRequest(address _a, address _b) internal view returns (TrustlineRequest memory) {
        TrustlineRequest memory trustlineRequest = requestedTrustlineUpdates[uniqueIdentifier(_a, _b)];
        return trustlineRequest;
    }

    function _deleteTrustlineRequest(address _a, address _b) internal {
        delete requestedTrustlineUpdates[uniqueIdentifier(_a, _b)];
    }

    function _storeTrustlineRequest(address _a, address _b, TrustlineRequest memory _trustlineRequest) internal {
        if (!customInterests) {
            assert(_trustlineRequest.interestRateGiven == defaultInterestRate);
            assert(_trustlineRequest.interestRateReceived == defaultInterestRate);
        } else {
            assert(_trustlineRequest.interestRateGiven >= 0);
            assert(_trustlineRequest.interestRateReceived >= 0);

        }

        TrustlineRequest storage trustlineRequest = requestedTrustlineUpdates[uniqueIdentifier(_a, _b)];

        trustlineRequest.creditlineGiven = _trustlineRequest.creditlineGiven;
        trustlineRequest.creditlineReceived = _trustlineRequest.creditlineReceived;
        trustlineRequest.interestRateGiven = _trustlineRequest.interestRateGiven;
        trustlineRequest.interestRateReceived = _trustlineRequest.interestRateReceived;
        trustlineRequest.initiator = _trustlineRequest.initiator;
        trustlineRequest.isFrozen = _trustlineRequest.isFrozen;
    }

    // in this function, it is assumed _creditor is the initator of the trustline update (see _requestTrustlineUpdate())
    function _updateTrustline(
        address _creditor,
        address _debtor,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived,
        int16 _interestRateGiven,
        int16 _interestRateReceived,
        bool _isFrozen
    )
        internal
        returns (bool success)
    {
        require(! isNetworkFrozen, "The network is frozen and trustlines cannot be updated.");
        TrustlineAgreement memory trustlineAgreement = _loadTrustlineAgreement(_creditor, _debtor);
        if (_isTrustlineFrozen(trustlineAgreement)) {
            require(! _isFrozen, "Trustline is frozen, it cannot be updated unless unfrozen.");
        }
        require(
            customInterests ||
            (_interestRateGiven == defaultInterestRate && _interestRateReceived == defaultInterestRate),
            "Interest rates given and received must be equal to default interest rates."
        );
        if (customInterests) {
            require(
                _interestRateGiven >= 0 && _interestRateReceived >= 0,
                "Only positive interest rates are supported."
            );
        }

        // reduction of creditlines and interests given is always possible if trustline is not frozen
        if (_creditlineGiven <= trustlineAgreement.creditlineGiven &&
            _creditlineReceived <= trustlineAgreement.creditlineReceived &&
            _interestRateGiven <= trustlineAgreement.interestRateGiven &&
            _interestRateReceived == trustlineAgreement.interestRateReceived &&
            _isFrozen == trustlineAgreement.isFrozen &&
            ! trustlineAgreement.isFrozen
        ) {
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
            return true;
        }

        TrustlineRequest memory trustlineRequest = _loadTrustlineRequest(_creditor, _debtor);

        // if original initiator is debtor, try to accept request
        if (trustlineRequest.initiator == _debtor) {
            if (_creditlineReceived <= trustlineRequest.creditlineGiven && _creditlineGiven <= trustlineRequest.creditlineReceived && _interestRateGiven <= trustlineRequest.interestRateReceived && _interestRateReceived == trustlineRequest.interestRateGiven && _isFrozen == trustlineRequest.isFrozen) {
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
                _applyOnboardingRules(_creditor, _debtor);

                return true;

            } else {
                _requestTrustlineUpdate(
                    _creditor,
                    _debtor,
                    _creditlineGiven,
                    _creditlineReceived,
                    _interestRateGiven,
                    _interestRateReceived,
                    _isFrozen
                );

                return true;
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
                _isFrozen
            );

            return true;
        }
    }

    function _updateCreditlimits(
        address _creditor,
        address _debtor,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived
    )
        internal
        returns (bool success)
    {
        int16 interestRateGiven = defaultInterestRate;
        int16 interestRateReceived = defaultInterestRate;
        TrustlineAgreement memory trustlineAgreement = _loadTrustlineAgreement(_creditor, _debtor);
        bool isFrozen = trustlineAgreement.isFrozen;
        if (customInterests) {
            interestRateGiven = trustlineAgreement.interestRateGiven;
            interestRateReceived = trustlineAgreement.interestRateReceived;
        }
        return _updateTrustline(
            _creditor,
            _debtor,
            _creditlineGiven,
            _creditlineReceived,
            interestRateGiven,
            interestRateReceived,
            isFrozen
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
    )
        internal
    {
        Trustline memory _trustline = _loadTrustline(_creditor, _debtor);

        // Because the interest rate might change, we need to apply interests.
        if ((_interestRateGiven != _trustline.agreement.interestRateGiven ||
            _interestRateReceived != _trustline.agreement.interestRateReceived
            ) && _trustline.balances.balance != 0) {
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

    function _addToDebt(address debtor, address creditor, int72 value) internal {
        int72 oldDebt = debt[uniqueIdentifier(debtor, creditor)];
        if (debtor < creditor) {
            int72 newDebt = _safeSum(oldDebt, value);
            debt[uniqueIdentifier(debtor, creditor)] = newDebt;
            emit DebtUpdate(debtor, creditor, newDebt);
        } else {
            int72 newDebt = _safeSum(oldDebt, -value);
            debt[uniqueIdentifier(debtor, creditor)] = newDebt;
            emit DebtUpdate(debtor, creditor, -newDebt);
        }
    }

    function _reduceDebt(address debtor, address creditor, uint64 value) internal {
        _addToDebt(debtor, creditor, - int72(value));
    }

    function _applyOnboardingRules(address a, address b) internal {
        if (onboarder[a] == address(0)) {
            if (onboarder[b] == address(0)) {
                onboarder[a] = NO_ONBOARDER;
                onboarder[b] = NO_ONBOARDER;
                emit Onboard(NO_ONBOARDER, a);
                emit Onboard(NO_ONBOARDER, b);
                return;
            } else {
                onboarder[a] = b;
                emit Onboard(b, a);
            }
        } else {
            if (onboarder[b] == address(0)) {
                onboarder[b] = a;
                emit Onboard(a, b);
            }
        }
    }

    function _requestTrustlineUpdate(
        address _creditor,
        address _debtor,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived,
        int16 _interestRateGiven,
        int16 _interestRateReceived,
        bool _isFrozen
    )
        internal
    {
        _storeTrustlineRequest(
            _creditor,
            _debtor,
            TrustlineRequest(
                _creditlineGiven,
                _creditlineReceived,
                _interestRateGiven,
                _interestRateReceived,
                _isFrozen,
                _creditor
                )
        );

        emit TrustlineUpdateRequest(
            _creditor,
            _debtor,
            _creditlineGiven,
            _creditlineReceived,
            _interestRateGiven,
            _interestRateReceived,
            _isFrozen
        );
    }

    function _calculateFees(
        uint64 _imbalanceGenerated,
        uint16 _capacityImbalanceFeeDivisor
    )
        internal pure
        returns (uint64)
    {
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
    )
        internal pure
        returns (uint64)
    {
        if (_capacityImbalanceFeeDivisor == 0 || _imbalanceGenerated == 0) {
            return 0;
        }
        // Calculate the fees in reverse with c * imbalance / (1 - c) = imbalance / (divisor - 1)
        // We round up using (imbalance - 1) / (divisor - 1) + 1
        return (_imbalanceGenerated - 1) / (_capacityImbalanceFeeDivisor - 1) + 1;
    }

    function _imbalanceGenerated(
        uint64 _value,
        int72 _balance
    )
        internal pure
        returns (uint64)
    {
        int72 imbalanceGenerated = int72(_value);
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
        uint64 result = uint64(imbalanceGenerated);
        require(result == imbalanceGenerated, "The imbalance does not fit into uint64.");
        return result;
    }

    function _calculateBalanceWithInterests(
        int72 _balance,
        uint _startTime,
        uint _endTime,
        int16 _interestRateGiven,
        int16 _interestRateReceived
    )
        internal
        pure
        returns (int72)
    {
        int16 rate = 0;
        if (_balance > 0) {
            rate = _interestRateGiven;
        }else {
            rate = _interestRateReceived;
        }


        int256 dt = int256(_endTime - _startTime);
        int256 intermediateOrder = _balance;
        int256 newBalance = _balance;

        assert(dt>=0);

        for (int i = 1; i <= 15; i++) {
            int256 newIntermediateOrder = intermediateOrder*rate*dt;

            //Overflow adjustment
            if ((newIntermediateOrder != 0) && (newIntermediateOrder / (rate * dt) != intermediateOrder)) {
                if (rate > 0) {
                    newBalance = MAX_BALANCE;
                } else {
                    newBalance = MIN_BALANCE;
                }
                break;
            }

            intermediateOrder = newIntermediateOrder/(SECONDS_PER_YEAR*10000*i);

            if (intermediateOrder == 0) {
                break;
            }

            newBalance += intermediateOrder;
            //Overflow adjustment
            if (newBalance > MAX_BALANCE) {
                newBalance = MAX_BALANCE;
                break;
            }
            if (newBalance < MIN_BALANCE) {
                newBalance = MIN_BALANCE;
                break;
            }
        }

        return int72(newBalance);
    }

    // Calculates a representation of how happy or unhappy a participant is because of the interests after a transfer
    // The higher the value returned, the higher the happiness of the sender and the higher the unhappiness of the receiver
    // This is called after the transfer has been done, so _trustline is the trustline from the senders view after the transfer
    // has been done. _balanceBefore is the sender's balance before the transfer has been done.
    function _interestHappiness(
        Trustline memory _trustline,
        int72 _balanceBefore
    )
        internal pure
        returns (int)
    {
        int72 _balance = _trustline.balances.balance;
        int72 transferredValue = _balanceBefore - _balance;

        if (_balanceBefore <= 0) {
            // Sender already owes receiver, this will only effect the interest rate received
            return - int(transferredValue) * _trustline.agreement.interestRateReceived;
        } else if (_balance >= 0) {
            // Receiver owes sender before and after the transfer. This only effects the interest rate received
            return - int(transferredValue) * _trustline.agreement.interestRateGiven;
        } else {
            // It effects both interest rates
            // Before the transfer: Receiver owes to sender balanceBefore;
            // After the transfer: Sender owes to receiver balance;
            return - int(_balanceBefore) * _trustline.agreement.interestRateGiven + int(_balance) * _trustline.agreement.interestRateReceived;
        }
    }

    // Returns whether a trustline is frozen
    // Should be more gas efficient than public isTrustlineFrozen() if agreement already loaded in memory
    function _isTrustlineFrozen(TrustlineAgreement memory agreement) internal view returns (bool) {
        if (isNetworkFrozen) {
            return true;
        }
        return agreement.isFrozen;
    }

    function uniqueIdentifier(address _a, address _b) internal pure returns (bytes32) {
        require(_a != _b, "Unique identifiers require different addresses");
        if (_a < _b) {
            return keccak256(abi.encodePacked(_a, _b));
        } else if (_a > _b) {
            return keccak256(abi.encodePacked(_b, _a));
        }
    }

    function acceptId(
        address _creditor,
        address _debtor
    )
        internal
        pure
        returns (bytes32)
    {
        return keccak256(abi.encodePacked(_creditor, _debtor));
    }

    function _safeSum(int72 a, int72 b) internal pure returns (int72 sum) {
        sum = a + b;
        if (a > 0 && b > 0) {
            require(sum > 0, "Overflow error.");
        }
        if (a < 0 && b < 0) {
            require(sum < 0, "Underflow error.");
        }
    }
}
