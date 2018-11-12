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
    mapping (bytes32 => Account) internal accounts;
    // mapping uniqueId => trustline request
    mapping (bytes32 => TrustlineRequest) internal requestedTrustlineUpdates;

    // friends, users address has an account with
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

    // for accounting balance and trustline between two users introducing fees and interests
    // currently uses 160 + 136 bits, 216 remaining to make two structs
    struct Account {
        // A < B (A is the lower address)

        uint64 creditlineGiven;        //  creditline given by A to B, always positive
        uint64 creditlineReceived;     //  creditline given by B to A, always positive

        int16 interestRateGiven;      //  interest rate set by A for creditline given by A to B in 0.01% per year
        int16 interestRateReceived;   //  interest rate set by B for creditline given from B to A in 0.01% per year

        uint16 feesOutstandingA;       //  fees outstanding by A
        uint16 feesOutstandingB;       //  fees outstanding by B

        uint32 mtime;                  //  last time interests were applied

        int72 balance;                 //  balance between A and B, balance is >0 if B owes A, negative otherwise.
                                       //  balance(B,A) = - balance(A,B)
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
    * Query the trustline account between two users.
    * Can be removed once structs are supported in the ABI
    */
    function getAccount(address _a, address _b) external view returns (int, int, int, int, int, int, int, int) {
        Account memory account = _loadAccount(_a, _b);

        return (
            account.creditlineGiven,
            account.creditlineReceived,
            account.interestRateGiven,
            account.interestRateReceived,
            account.feesOutstandingA,
            account.feesOutstandingB,
            account.mtime,
            account.balance);
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

    /* close message sender's trustline with _otherParty by doing a triangular
       transfer along the given _path */
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
        Account memory account = _loadAccount(_spender, _receiver);
        int72 balance = account.balance;
        uint64 creditline = account.creditlineReceived;
        remaining = uint(creditline + balance);
    }

    /**
     * @notice The creditline limit given by `_creditor` to `_debtor`
     * @return Amount tokens allowed to spent
     */
    function creditline(address _creditor, address _debtor) public constant returns (uint _creditline) {
        // returns the current creditline given by A to B
        Account memory account = _loadAccount(_creditor, _debtor);
        _creditline = account.creditlineGiven;
    }

    /**
     * @notice The interest rate given by `_creditor` to `_debtor`
     * @return Interest rate on the balance of the line
     */
    function interestRate(address _creditor, address _debtor) public constant returns (int16 _interestRate) {
        // returns the current interests given by A to B
        Account memory account = _loadAccount(_creditor, _debtor);
        _interestRate = account.interestRateGiven;
    }

    /*
     * @notice returns what B owes to A
     */
    function balance(address _a, address _b) public constant returns (int _balance) {
        Account memory account = _loadAccount(_a, _b);
        _balance = account.balance;
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

    // This function modifies the value of the balance stored in the account for sender and receiver.
    // It calculates the fees, applies them to the balance and returns them.
    // We ask this function to apply the interests too for optimisation (only one call to _storeAccount)
    function _applyDirectTransfer(
        Account memory _account,
        uint64 _value
    )
        internal
    {
        int72 newBalance = _account.balance - _value;
        require(newBalance <= _account.balance);

        // check if creditline is not exceeded
        uint64 creditlineReceived = _account.creditlineReceived;
        require(-newBalance <= int72(creditlineReceived));

        _account.balance = newBalance;
    }

    function _applyInterests(
        Account memory _account
    )
        internal
    {
        _account.balance = _calculateBalanceWithInterests(
            _account.balance,
            _account.mtime,
            now,
            _account.interestRateGiven,
            _account.interestRateReceived
        );
        _account.mtime = uint32(now);
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
            if (i == 1) {
                sender = _from;
            } else {
                sender = _path[i-2];
            }
            // Load account only once at the beginning
            Account memory account = _loadAccount(sender, _path[i-1]);
            _applyInterests(account);

            uint64 fee = _calculateFees(forwardedValue, account.balance, capacityImbalanceFeeDivisor);
            // forward the value + the fee
            forwardedValue += fee;
            //Overflow check
            require(forwardedValue >= fee);
            fees += fee;
            require(fees <= _maxFee);


            int72 balanceBefore = account.balance;

            _applyDirectTransfer(
                account,
                forwardedValue);


            if (preventMediatorInterests) {
                // prevent intermediaries from paying more interests than they receive
                // unless the transaction helps in reducing the debt of the next hop in the path
                receiverHappiness = receiverUnhappiness;  // receiver was the sender in last iteration
                receiverUnhappiness = _interestHappiness(account, balanceBefore);
                require(receiverUnhappiness <= receiverHappiness || reducingDebtOfNextHopOnly);
                reducingDebtOfNextHopOnly = account.balance >= 0;
            }

            // store account only once at the end
            _storeAccount(sender, _path[i-1], account);
            // Should be removed later
            emit BalanceUpdate(sender, _path[i-1], account.balance);
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
            // Load account only once at the beginning
            Account memory account = _loadAccount(sender, _path[i]);
            _applyInterests(account);

            uint64 fee = _calculateFees(forwardedValue, account.balance, capacityImbalanceFeeDivisor);
            // forward the value minus the fee
            require(forwardedValue>=fee);
            forwardedValue -= fee;
            //Overflow check
            require(forwardedValue >= fee);
            fees += fee;
            require(fees <= _maxFee);


            int72 balanceBefore = account.balance;

            _applyDirectTransfer(
                account,
                forwardedValue);


            if (preventMediatorInterests) {
                // prevent intermediaries from paying more interests than they receive
                // unless the transaction helps in reducing the debt of the next hop in the path
                receiverHappiness = receiverUnhappiness;  // receiver was the sender in last iteration
                receiverUnhappiness = _interestHappiness(account, balanceBefore);
                require(receiverUnhappiness <= receiverHappiness || reducingDebtOfNextHopOnly);
                reducingDebtOfNextHopOnly = account.balance >= 0;
            }

            // store account only once at the end
            _storeAccount(sender, _path[i], account);
            // Should be removed later
            emit BalanceUpdate(sender, _path[i], account.balance);
        }

        return true;
    }

    /* close a trustline, which must have a balance of zero */
    function _closeTrustline(
        address _from,
        address _otherParty)
        internal
    {
        Account memory account = _loadAccount(_from, _otherParty);
        assert(account.balance == 0);

        delete accounts[uniqueIdentifier(_from, _otherParty)];
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
        Account memory account = _loadAccount(_from, _otherParty);
        _applyInterests(account);
        /* we could as well call _storeAccount here. It doesn't matter for the
           _mediatedTransfer/_mediatedTransferReceiverPays calls below since the
           interest will be recomputed if we don't call storeAccount here. We
           may investigate what's cheaper gas-wise later.

         _storeAccount(_from, _otherParty, account);
        */
        if (account.balance > 0) {
            require(_path.length >= 2 && _from == _path[_path.length - 1] && _path[0] == _otherParty);
            _mediatedTransferReceiverPays(
                _from,
                _from,
                uint32(account.balance),
                _maxFee,
                _path);
        } else if (account.balance < 0) {
            require(_path.length >= 2 && _from == _path[_path.length - 1] && _path[_path.length - 2] == _otherParty);
            _mediatedTransfer(
                _from,
                _from,
                uint32(-account.balance),
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
        Account memory account;

        account.creditlineGiven = _creditlineGiven;
        account.creditlineReceived = _creditlineReceived;
        account.interestRateGiven = _interestRateGiven;
        account.interestRateReceived = _interestRateReceived;
        account.feesOutstandingA = _feesOutstandingA;
        account.feesOutstandingB = _feesOutstandingB;
        account.mtime = _mtime;
        account.balance = _balance;

        _storeAccount(_a, _b, account);

        addToUsersAndFriends(_a, _b);
    }

    function _loadAccount(address _a, address _b) internal constant returns (Account) {
        Account memory account = accounts[uniqueIdentifier(_a, _b)];
        Account memory result;
        if (_a < _b) {
            result = account;
        } else {
            result.creditlineReceived = account.creditlineGiven;
            result.creditlineGiven = account.creditlineReceived;
            result.interestRateReceived = account.interestRateGiven;
            result.interestRateGiven = account.interestRateReceived;
            result.feesOutstandingB = account.feesOutstandingA;
            result.feesOutstandingA = account.feesOutstandingB;
            result.mtime = account.mtime;
            result.balance = -account.balance; // balance is value receiver owes sender
        }
        return result;
    }

    // Provides the abstraction of whether a < b or b < a.
    function _storeAccount(address _a, address _b, Account account) internal {
        if (!customInterests) {
            assert(account.interestRateGiven == defaultInterestRate);
            assert(account.interestRateReceived == defaultInterestRate);
        } else {
            assert(account.interestRateGiven >= 0);
            assert(account.interestRateReceived >= 0);
        }

        Account storage acc = accounts[uniqueIdentifier(_a, _b)];
        if (_a < _b) {
            acc.creditlineGiven = account.creditlineGiven;
            acc.creditlineReceived = account.creditlineReceived;
            acc.interestRateGiven = account.interestRateGiven;
            acc.interestRateReceived = account.interestRateReceived;
            acc.feesOutstandingA = account.feesOutstandingA;
            acc.feesOutstandingB = account.feesOutstandingB;
            acc.mtime = account.mtime;
            acc.balance = account.balance;
        } else {
            acc.creditlineReceived = account.creditlineGiven;
            acc.creditlineGiven = account.creditlineReceived;
            acc.interestRateReceived = account.interestRateGiven;
            acc.interestRateGiven = account.interestRateReceived;
            acc.feesOutstandingB = account.feesOutstandingA;
            acc.feesOutstandingA = account.feesOutstandingB;
            acc.mtime = account.mtime;
            acc.balance = - account.balance;
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
        Account memory account = _loadAccount(_creditor, _debtor);

        // reduce of creditlines and interests given is always possible
        if (_creditlineGiven <= account.creditlineGiven && _creditlineReceived <= account.creditlineReceived && _interestRateGiven <= account.interestRateGiven && _interestRateReceived == account.interestRateReceived) {
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
            Account memory account = _loadAccount(_creditor, _debtor);
            interestRateGiven = account.interestRateGiven;
            interestRateReceived = account.interestRateReceived;
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
        Account memory _account = _loadAccount(_creditor, _debtor);

        // Because the interest rate might change, we need to apply interests.
        _applyInterests(_account);

        addToUsersAndFriends(_creditor, _debtor);
        _account.creditlineGiven = _creditlineGiven;
        _account.creditlineReceived = _creditlineReceived;
        _account.interestRateGiven = _interestRateGiven;
        _account.interestRateReceived = _interestRateReceived;
        _storeAccount(_creditor, _debtor, _account);

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
    // This is called after the transfer has been done, so _account is the account from the senders view after the transfer
    // has been done. _balanceBefore is the sender's balance before the transfer has been done.
    function _interestHappiness(
        Account memory _account,
        int72 _balanceBefore
    )
        internal view
        returns (int)
    {
        int72 balance = _account.balance;
        int72 transferredValue = _balanceBefore - balance;

        if (_balanceBefore <= 0) {
            // Sender already owes receiver, this will only effect the interest rate received
            return - int(transferredValue) * _account.interestRateReceived;
        } else if (balance >= 0) {
            // Receiver owes sender before and after the transfer. This only effects the interest rate received
            return - int(transferredValue) * _account.interestRateGiven;
        } else {
            // It effects both interest rates
            // Before the transfer: Receiver owes to sender balanceBefore;
            // After the transfer: Sender owes to receiver balance;
            return - int(_balanceBefore) * _account.interestRateGiven + int(balance) * _account.interestRateReceived;
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
