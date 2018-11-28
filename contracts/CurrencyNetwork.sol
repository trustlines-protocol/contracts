pragma solidity ^0.4.21;


import "./lib/it_set_lib.sol";
import "./lib/ECVerify.sol";
import "./tokens/Receiver_Interface.sol";
import "./lib/Ownable.sol";
import "./lib/Destructable.sol";
import "./lib/Authorizable.sol";
import "./CurrencyNetworkInterface.sol";


/**
 * CurrencyNetwork
 *
 * Main contract of Trustlines, encapsulates all trustlines of one currency network.
 * Implements functions to ripple payments in a currency network. Implements core features of ERC20
 *
 **/
contract CurrencyNetwork is CurrencyNetworkInterface, Ownable, Authorizable, Destructable {

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
    //list of all users of the system
    ItSet.AddressSet internal users;

    // Divides current value being transferred to calculate the capacity fee which equals the imbalance fee
    uint16 public capacityImbalanceFeeDivisor;

    // meta data for token part
    string public name;
    string public symbol;
    uint8 public decimals;

    // interests settings, interests are expressed in 0.01% per year
    int16 public defaultInterestRate;
    bool public customInterests;
    bool public preventMediatorInterests;

    // Events
    event Transfer(address indexed _from, address indexed _to, uint _value);

    event TrustlineUpdateRequest(
        address indexed _creditor,
        address indexed _debtor,
        uint _creditlineGiven,
        uint _creditlineReceived,
        int _interestRateGiven,
        int _interestRateReceived
    );

    event TrustlineUpdate(
        address indexed _creditor,
        address indexed _debtor,
        uint _creditlineGiven,
        uint _creditlineReceived,
        int _interestRateGiven,
        int _interestRateReceived
    );

    event BalanceUpdate(address indexed _from, address indexed _to, int256 _value);

    // for accounting balance and trustline agreement between two users introducing fees and interests
    // currently uses 160 + 136 bits, 216 remaining to make two structs
    struct Trustline {
        // A < B (A is the lower address)
        TrustlineAgreement agreement;
        TrustlineBalances balances;
    }

    struct TrustlineAgreement {

        uint64 creditlineGiven;        //  creditline given by A to B, always positive
        uint64 creditlineReceived;     //  creditline given by B to A, always positive

        int16 interestRateGiven;      //  interest rate set by A for creditline given by A to B in 0.01% per year
        int16 interestRateReceived;   //  interest rate set by B for creditline given from B to A in 0.01% per year

        int96 padding;                //  fill up to 256bit
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
        address initiator;
    }

    modifier notSender(address _sender) {
        require(_sender != msg.sender);
        _;
    }

    // check value is inbounds for accounting to prevent overflows
    modifier valueWithinInt32(uint _value) {
        require(_value < 2 ** 32);
        _;
    }

    function CurrencyNetwork() public {
        // don't do anything here due to upgradeability issues (no contructor-call on replacement).
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
     */
    function init(
        string _name,
        string _symbol,
        uint8 _decimals,
        uint16 _capacityImbalanceFeeDivisor,
        int16 _defaultInterestRate,
        bool _customInterests,
        bool _preventMediatorInterests
    )
        onlyOwner
        external
    {
        // verifies that only one parameter is selected.
        require(! ((_defaultInterestRate != 0) && _customInterests));
        require(!_preventMediatorInterests || (_preventMediatorInterests && _customInterests));

        name = _name;
        symbol = _symbol;
        decimals = _decimals;
        capacityImbalanceFeeDivisor = _capacityImbalanceFeeDivisor;
        defaultInterestRate = _defaultInterestRate;
        customInterests = _customInterests;
        preventMediatorInterests = _preventMediatorInterests;
    }

    /**
     * @notice send `_value` token to `_to` from `msg.sender`
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @param _maxFee Maximum fee the sender wants to pay
     * @param _path Path between msg.sender and _to
     **/
    function transfer(
        address _to,
        uint64 _value,
        uint64 _maxFee,
        address[] _path
    )
        external
        returns (bool _success)
    {
        _success = _mediatedTransfer(
            msg.sender,
            _to,
            _value,
            _maxFee,
            _path);

        if (_success) {
            emit Transfer(
                msg.sender,
                _to,
                _value);
        }
    }

    /**
     * @notice send `_value` token to `_to` from `_from`
     * msg.sender needs to be authorized to call this function
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @param _maxFee Maximum fee the sender wants to pay
     * @param _path Path between msg.sender and _to
     **/
    function transferFrom(
        address _from,
        address _to,
        uint64 _value,
        uint64 _maxFee,
        address[] _path
    )
        external
        returns (bool success)
    {
        require(authorized[msg.sender]);

        success = _mediatedTransfer(
            _from,
            _to,
            _value,
            _maxFee,
            _path);

        if (success) {
            emit Transfer(
                _from,
                _to,
                _value);
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
     * @return true, if the credit was successful
     */
    function updateTrustline(
        address _debtor,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived,
        int16 _interestRateGiven,
        int16 _interestRateReceived
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
            _interestRateReceived
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
    function updateTrustline(
        address _debtor,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived
    )
        external
        returns (bool _success)
    {
        address _creditor = msg.sender;

        return _updateTrustline(
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
     * @return true, if the credit was successful
     */
    function updateTrustlineDefaultInterests(
        address _debtor,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived
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
            defaultInterestRate
        );
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
    function getAccount(address _a, address _b) external view returns (int, int, int, int, int, int, int, int) {
        Trustline memory trustline = _loadTrustline(_a, _b);

        return (
            trustline.agreement.creditlineGiven,
            trustline.agreement.creditlineReceived,
            trustline.agreement.interestRateGiven,
            trustline.agreement.interestRateReceived,
            trustline.balances.feesOutstandingA,
            trustline.balances.feesOutstandingB,
            trustline.balances.mtime,
            trustline.balances.balance);
    }

    function getAccountLen() external pure returns (uint) {
        return 8 * 32 + 2;
    }

    /**
    * Set the trustline account between two users.
    * Can be removed once structs are supported in the ABI
    */
    function setAccount(
        address _a,
        address _b,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived,
        int16 _interestRateGiven,
        int16 _interestRateReceived,
        uint16 _feesOutstandingA,
        uint16 _feesOutstandingB,
        uint32 _mtime,
        int72 _balance
    )
        onlyOwner
        external
    {
        require(customInterests || (_interestRateGiven == defaultInterestRate && _interestRateReceived == defaultInterestRate));
        if (customInterests) {
            require(_interestRateGiven >= 0 && _interestRateReceived >= 0);
        }

        _setAccount(
            _a,
            _b,
            _creditlineGiven,
            _creditlineReceived,
            _interestRateGiven,
            _interestRateReceived,
            _feesOutstandingA,
            _feesOutstandingB,
            _mtime,
            _balance
        );
    }

    /**
    * Set the trustline account between two users with default interests.
    * Can be removed once structs are supported in the ABI
    */
    function setAccountDefaultInterests(
        address _a,
        address _b,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived,
        uint16 _feesOutstandingA,
        uint16 _feesOutstandingB,
        uint32 _mtime,
        int72 _balance
    )
        onlyOwner
        external
    {
        _setAccount(
            _a,
            _b,
            _creditlineGiven,
            _creditlineReceived,
            defaultInterestRate,
            defaultInterestRate,
            _feesOutstandingA,
            _feesOutstandingB,
            _mtime,
            _balance
        );
    }

    /** @notice Close the trustline between `msg.sender` and `_otherParty` by doing a triangular transfer over `_path
        @param _otherParty Address of the other party to close the trustline with
        @param _maxFee maximum fees the sender is willing to pay
        @param _path The path along, which to do the triangulation
     */
    function closeTrustlineByTriangularTransfer(
        address _otherParty,
        uint32 _maxFee,
        address[] _path
    )
        external
    {
        _closeTrustlineByTriangularTransfer(msg.sender, _otherParty, _maxFee, _path);
    }

    /**
     * @notice Checks for the spendable amount by spender
     * @param _spender The address from which the balance will be retrieved
     * @return spendable The spendable amount
     */
    function spendable(address _spender) public constant returns (uint _spendable) {
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
    function spendableTo(address _spender, address _receiver) public constant returns (uint remaining) {
        Trustline memory trustline = _loadTrustline(_spender, _receiver);
        int72 balance = trustline.balances.balance;
        uint64 creditline = trustline.agreement.creditlineReceived;
        remaining = uint(creditline + balance);
    }

    /**
     * @notice The creditline limit given by `_creditor` to `_debtor`
     * @return Amount tokens allowed to spent
     */
    function creditline(address _creditor, address _debtor) public constant returns (uint _creditline) {
        // returns the current creditline given by A to B
        TrustlineAgreement memory trustlineAgreement = _loadTrustlineAgreement(_creditor, _debtor);
        _creditline = trustlineAgreement.creditlineGiven;
    }

    /**
     * @notice The interest rate given by `_creditor` to `_debtor`
     * @return Interest rate on the balance of the line
     */
    function interestRate(address _creditor, address _debtor) public constant returns (int16 _interestRate) {
        // returns the current interests given by A to B
        TrustlineAgreement memory trustlineAgreement = _loadTrustlineAgreement(_creditor, _debtor);
        _interestRate = trustlineAgreement.interestRateGiven;
    }

    /*
     * @notice returns what B owes to A
     */
    function balance(address _a, address _b) public constant returns (int _balance) {
        TrustlineBalances memory trustlineBalances = _loadTrustlineBalances(_a, _b);
        _balance = trustlineBalances.balance;
    }

    function getFriends(address _user) public constant returns (address[]) {
        return friends[_user].list;
    }

    function getFriendsReturnSize(address _user) public constant returns (uint) {
        return getFriends(_user).length + 2;
    }

    function getUsers() public constant returns (address[]) {
        return users.list;
    }

    function getUsersReturnSize() public constant returns (uint) {
        // Returning a dynamically-sized array requires two extra slots.
        // One for the data location pointer, and one for the length.
        return getUsers().length + 2;
    }

    function name() public constant returns (string) {
        return name;
    }

    function nameLen() public constant returns (uint) {
        return bytes(name).length;
    }

    function symbol() public constant returns (string) {
        return symbol;
    }

    function symbolLen() public constant returns (uint) {
        return bytes(symbol).length;
    }

    function decimals() public constant returns (uint8) {
        return decimals;
    }

    // This function transfers value over this trustline
    // For that it modifies the value of the balance stored in the trustline for sender and receiver
    function _applyDirectTransfer(
        Trustline memory _trustline,
        uint64 _value
    )
        internal
    {
        int72 newBalance = _trustline.balances.balance - _value;
        require(newBalance <= _trustline.balances.balance);

        // check if creditline is not exceeded
        uint64 creditlineReceived = _trustline.agreement.creditlineReceived;
        require(-newBalance <= int72(creditlineReceived));

        _trustline.balances.balance = newBalance;
    }

    function _applyInterests(
        Trustline memory _trustline
    )
        internal
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

    function _mediatedTransfer(
        address _from,
        address _to,
        uint64 _value,
        uint64 _maxFee,
        address[] _path
    )
        internal
        returns (bool)
    {
        // check Path: is there a Path and is _to the last address? Otherwise throw
        require((_path.length > 0) && (_to == _path[_path.length - 1]));

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
            _applyInterests(trustline);

            if (i == _path.length) {
                fee = 0; // receiver should not get a fee
            } else {
                fee = _calculateFees(forwardedValue, trustline.balances.balance, capacityImbalanceFeeDivisor);
            }

            // forward the value + the fee
            forwardedValue += fee;
            //Overflow check
            require(forwardedValue >= fee);
            fees += fee;
            require(fees <= _maxFee);


            int72 balanceBefore = trustline.balances.balance;

            _applyDirectTransfer(
                trustline,
                forwardedValue);


            if (preventMediatorInterests) {
                // prevent intermediaries from paying more interests than they receive
                // unless the transaction helps in reducing the debt of the next hop in the path
                receiverHappiness = receiverUnhappiness;  // receiver was the sender in last iteration
                receiverUnhappiness = _interestHappiness(trustline, balanceBefore);
                require(receiverUnhappiness <= receiverHappiness || reducingDebtOfNextHopOnly);
                reducingDebtOfNextHopOnly = trustline.balances.balance >= 0;
            }

            // store only balance because trustline agreement did not change
            _storeTrustlineBalances(sender, _path[i-1], trustline.balances);
            // Should be removed later
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
        address[] _path
    )
        internal
        returns (bool)
    {
        // check Path: is there a Path and is _to the last address? Otherwise throw
        require((_path.length > 0) && (_to == _path[_path.length - 1]));

        uint64 forwardedValue = _value;
        uint64 fees = 0;
        int receiverUnhappiness = 0;
        int receiverHappiness = 0;
        bool reducingDebtOfNextHopOnly = true;

        // check path starting from sender correctly accumulate the fee
        for (uint i = 0; i < _path.length; i++) {
            // the address of the receiver is _path[i]
            address sender;
            if (i == 0) {
                sender = _from;
            } else {
                sender = _path[i-1];
            }
            // Load trustline only once at the beginning
            Trustline memory trustline = _loadTrustline(sender, _path[i]);
            _applyInterests(trustline);

            uint64 fee = _calculateFees(forwardedValue, trustline.balances.balance, capacityImbalanceFeeDivisor);
            // forward the value minus the fee
            require(forwardedValue>=fee);
            forwardedValue -= fee;
            //Overflow check
            require(forwardedValue >= fee);
            fees += fee;
            require(fees <= _maxFee);


            int72 balanceBefore = trustline.balances.balance;

            _applyDirectTransfer(
                trustline,
                forwardedValue);


            if (preventMediatorInterests) {
                // prevent intermediaries from paying more interests than they receive
                // unless the transaction helps in reducing the debt of the next hop in the path
                receiverHappiness = receiverUnhappiness;  // receiver was the sender in last iteration
                receiverUnhappiness = _interestHappiness(trustline, balanceBefore);
                require(receiverUnhappiness <= receiverHappiness || reducingDebtOfNextHopOnly);
                reducingDebtOfNextHopOnly = trustline.balances.balance >= 0;
            }

            // store only balance because trustline agreement did not change
            _storeTrustlineBalances(sender, _path[i], trustline.balances);
            // Should be removed later
            emit BalanceUpdate(sender, _path[i], trustline.balances.balance);
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
        assert(balances.balance == 0);

        delete trustlines[uniqueIdentifier(_from, _otherParty)];
        friends[_from].remove(_otherParty);
        friends[_otherParty].remove(_from);
        emit TrustlineUpdate(
            _from,
            _otherParty,
            0,
            0,
            0,
            0);
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
        address[] _path)
        internal
    {
        Trustline memory trustline = _loadTrustline(_from, _otherParty);
        _applyInterests(trustline);
        /* we could as well call _storeTrustlineBalances here. It doesn't matter for the
           _mediatedTransfer/_mediatedTransferReceiverPays calls below since the
           interest will be recomputed if we don't call storeTrustlineBalances here. We
           may investigate what's cheaper gas-wise later.
        */
        TrustlineBalances memory balances = trustline.balances;
        if (balances.balance > 0) {
            require(_path.length >= 2 && _from == _path[_path.length - 1] && _path[0] == _otherParty);
            _mediatedTransferReceiverPays(
                _from,
                _from,
                uint32(balances.balance),
                _maxFee,
                _path);
        } else if (balances.balance < 0) {
            require(_path.length >= 2 && _from == _path[_path.length - 1] && _path[_path.length - 2] == _otherParty);
            _mediatedTransfer(
                _from,
                _from,
                uint32(-balances.balance),
                _maxFee,
                _path);
        } else {
            /* balance is zero, there's nothing to do here */
        }

        _closeTrustline(_from, _otherParty);
    }

    function addToUsersAndFriends(address _a, address _b) internal {
        users.insert(_a);
        users.insert(_b);
        friends[_a].insert(_b);
        friends[_b].insert(_a);
    }

    function _setAccount(
        address _a,
        address _b,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived,
        int16 _interestRateGiven,
        int16 _interestRateReceived,
        uint16 _feesOutstandingA,
        uint16 _feesOutstandingB,
        uint32 _mtime,
        int72 _balance
    )
        internal
    {
        TrustlineAgreement memory trustlineAgreement;
        trustlineAgreement.creditlineGiven = _creditlineGiven;
        trustlineAgreement.creditlineReceived = _creditlineReceived;
        trustlineAgreement.interestRateGiven = _interestRateGiven;
        trustlineAgreement.interestRateReceived = _interestRateReceived;

        TrustlineBalances memory trustlineBalances;
        trustlineBalances.feesOutstandingA = _feesOutstandingA;
        trustlineBalances.feesOutstandingB = _feesOutstandingB;
        trustlineBalances.mtime = _mtime;
        trustlineBalances.balance = _balance;

        _storeTrustlineAgreement(_a, _b, trustlineAgreement);
        _storeTrustlineBalances(_a, _b, trustlineBalances);

        addToUsersAndFriends(_a, _b);
    }

    function _loadTrustline(address _a, address _b) internal constant returns (Trustline) {
        Trustline memory trustline;
        trustline.agreement = _loadTrustlineAgreement(_a, _b);
        trustline.balances = _loadTrustlineBalances(_a, _b);
        return trustline;
    }

    function _loadTrustlineAgreement(address _a, address _b) internal constant returns (TrustlineAgreement) {
        TrustlineAgreement memory trustlineAgreement = trustlines[uniqueIdentifier(_a, _b)].agreement;
        TrustlineAgreement memory result;
        if (_a < _b) {
            result = trustlineAgreement;
        } else {
            result.creditlineReceived = trustlineAgreement.creditlineGiven;
            result.creditlineGiven = trustlineAgreement.creditlineReceived;
            result.interestRateReceived = trustlineAgreement.interestRateGiven;
            result.interestRateGiven = trustlineAgreement.interestRateReceived;
        }
        return result;
    }

    function _loadTrustlineBalances(address _a, address _b) internal constant returns (TrustlineBalances) {
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
            storedTrustlineAgreement.padding = trustlineAgreement.padding;
        } else {
            storedTrustlineAgreement.creditlineGiven = trustlineAgreement.creditlineReceived;
            storedTrustlineAgreement.creditlineReceived = trustlineAgreement.creditlineGiven;
            storedTrustlineAgreement.interestRateGiven = trustlineAgreement.interestRateReceived;
            storedTrustlineAgreement.interestRateReceived = trustlineAgreement.interestRateGiven;
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

    function _loadTrustlineRequest(address _a, address _b) internal constant returns (TrustlineRequest) {
        TrustlineRequest memory trustlineRequest = requestedTrustlineUpdates[uniqueIdentifier(_a, _b)];
        return trustlineRequest;
    }

    function _storeTrustlineRequest(address _a, address _b, TrustlineRequest _trustlineRequest) internal {
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
    }

    // in this function, it is assumed _creditor is the initator of the trustline update (see _requestTrustlineUpdate())
    function _updateTrustline(
        address _creditor,
        address _debtor,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived,
        int16 _interestRateGiven,
        int16 _interestRateReceived
    )
        internal
        returns (bool success)
    {
        require(
            customInterests ||
            (_interestRateGiven == defaultInterestRate && _interestRateReceived == defaultInterestRate)
        );
        if (customInterests) {
            require(_interestRateGiven >= 0 && _interestRateReceived >= 0);
        }
        TrustlineAgreement memory trustlineAgreement = _loadTrustlineAgreement(_creditor, _debtor);

        // reduce of creditlines and interests given is always possible
        if (_creditlineGiven <= trustlineAgreement.creditlineGiven && _creditlineReceived <= trustlineAgreement.creditlineReceived && _interestRateGiven <= trustlineAgreement.interestRateGiven && _interestRateReceived == trustlineAgreement.interestRateReceived) {
            _setTrustline(
                _creditor,
                _debtor,
                _creditlineGiven,
                _creditlineReceived,
                _interestRateGiven,
                _interestRateReceived
            );
            return true;
        }

        TrustlineRequest memory trustlineRequest = _loadTrustlineRequest(_creditor, _debtor);

        // if original initiator is debtor, try to accept request
        if (trustlineRequest.initiator == _debtor) {
            if (_creditlineReceived <= trustlineRequest.creditlineGiven && _creditlineGiven <= trustlineRequest.creditlineReceived && _interestRateGiven <= trustlineRequest.interestRateReceived && _interestRateReceived == trustlineRequest.interestRateGiven) {
                // _debtor and _creditor is switched because we want the initiator of the trustline to be _debtor.
                // So every Given / Received has to be switched.
                _setTrustline(
                    _debtor,
                    _creditor,
                    _creditlineReceived,
                    _creditlineGiven,
                    _interestRateReceived,
                    _interestRateGiven
                );

                return true;

            } else {
                _requestTrustlineUpdate(
                    _creditor,
                    _debtor,
                    _creditlineGiven,
                    _creditlineReceived,
                    _interestRateGiven,
                    _interestRateReceived
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
                _interestRateReceived
            );

            return true;
        }
    }

    function _updateTrustline(
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
        if (customInterests) {
            TrustlineAgreement memory trustlineAgreement = _loadTrustlineAgreement(_creditor, _debtor);
            interestRateGiven = trustlineAgreement.interestRateGiven;
            interestRateReceived = trustlineAgreement.interestRateReceived;
        }
        return _updateTrustline(
            _creditor,
            _debtor,
            _creditlineGiven,
            _creditlineReceived,
            interestRateGiven,
            interestRateReceived);
    }

    // Actually change the trustline
    function _setTrustline(
        address _creditor,
        address _debtor,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived,
        int16 _interestRateGiven,
        int16 _interestRateReceived
    )
        internal
    {
        Trustline memory _trustline = _loadTrustline(_creditor, _debtor);

        // Because the interest rate might change, we need to apply interests.
        _applyInterests(_trustline);

        addToUsersAndFriends(_creditor, _debtor);
        _trustline.agreement.creditlineGiven = _creditlineGiven;
        _trustline.agreement.creditlineReceived = _creditlineReceived;
        _trustline.agreement.interestRateGiven = _interestRateGiven;
        _trustline.agreement.interestRateReceived = _interestRateReceived;
        _storeTrustlineBalances(_creditor, _debtor, _trustline.balances);
        _storeTrustlineAgreement(_creditor, _debtor, _trustline.agreement);

        emit TrustlineUpdate(
            _creditor,
            _debtor,
            _creditlineGiven,
            _creditlineReceived,
            _interestRateGiven,
            _interestRateReceived
        );
    }

    function _requestTrustlineUpdate(
        address _creditor,
        address _debtor,
        uint64 _creditlineGiven,
        uint64 _creditlineReceived,
        int16 _interestRateGiven,
        int16 _interestRateReceived
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
                _creditor)
        );

        emit TrustlineUpdateRequest(
            _creditor,
            _debtor,
            _creditlineGiven,
            _creditlineReceived,
            _interestRateGiven,
            _interestRateReceived
        );
    }

    function _calculateFees(
        uint64 _value,
        int72 _balance,
        uint16 _capacityImbalanceFeeDivisor
    )
        internal pure
        returns (uint64)
    {
        if (_capacityImbalanceFeeDivisor == 0) {
            return 0;
        }

        int72 imbalanceGenerated = int72(_value);
        if (_balance > 0) {
            imbalanceGenerated = _value - _balance;
            if (imbalanceGenerated <= 0) {
                return 0;
            }
            // Overflow
            if (imbalanceGenerated > _value) {
                return 0;
            }
        }
        require(uint64(imbalanceGenerated) == imbalanceGenerated);
        return uint64(uint64(imbalanceGenerated) / _capacityImbalanceFeeDivisor + 1);  // minimum fee is 1
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
        internal view
        returns (int)
    {
        int72 balance = _trustline.balances.balance;
        int72 transferredValue = _balanceBefore - balance;

        if (_balanceBefore <= 0) {
            // Sender already owes receiver, this will only effect the interest rate received
            return - int(transferredValue) * _trustline.agreement.interestRateReceived;
        } else if (balance >= 0) {
            // Receiver owes sender before and after the transfer. This only effects the interest rate received
            return - int(transferredValue) * _trustline.agreement.interestRateGiven;
        } else {
            // It effects both interest rates
            // Before the transfer: Receiver owes to sender balanceBefore;
            // After the transfer: Sender owes to receiver balance;
            return - int(_balanceBefore) * _trustline.agreement.interestRateGiven + int(balance) * _trustline.agreement.interestRateReceived;
        }
    }

    function uniqueIdentifier(address _a, address _b) internal pure returns (bytes32) {
        require(_a != _b);
        if (_a < _b) {
            return keccak256(_a, _b);
        } else if (_a > _b) {
            return keccak256(_b, _a);
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
        return keccak256(_creditor, _debtor);
    }

}
