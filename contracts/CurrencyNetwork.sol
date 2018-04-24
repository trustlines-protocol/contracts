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

    using ItSet for ItSet.AddressSet;
    mapping (bytes32 => Account) internal accounts;
    // mapping acceptId => creditline value
    mapping (bytes32 => uint32) internal requestedCreditlineUpdates;
    // mapping uniqueId => trustline request
    mapping (bytes32 => TrustlineRequest) internal requestedTrustlineUpdates;

    // friends, users address has an account with
    mapping (address => ItSet.AddressSet) internal friends;
    //list of all users of the system
    ItSet.AddressSet internal users;

    // Divides current value being transferred to calculate the capacity fee which equals the imbalance fee
    uint16 internal capacityImbalanceFeeDivisor;

    // meta data for token part
    string public name;
    string public symbol;
    uint8 public decimals;

    // Events
    event Transfer(address indexed _from, address indexed _to, uint _value);
    event CreditlineUpdateRequest(address indexed _creditor, address indexed _debtor, uint _value);
    event CreditlineUpdate(address indexed _creditor, address indexed _debtor, uint _value);
    event TrustlineUpdateRequest(address indexed _creditor, address indexed _debtor, uint _creditlineGiven, uint _creditlineReceived);
    event TrustlineUpdate(address indexed _creditor, address indexed _debtor, uint _creditlineGiven, uint _creditlineReceived);

    event BalanceUpdate(address indexed _from, address indexed _to, int256 _value);

    // for accounting balance and trustline between two users introducing fees and interests
    // currently uses 208 bits, 48 remaining
    struct Account {
        // A < B (A is the lower address)

        uint32 creditlineGiven;        //  creditline given by A to B, always positive
        uint32 creditlineReceived;     //  creditline given by B to A, always positive

        uint16 interestRateGiven;      //  interest rate set by A for creditline given by A to B
        uint16 interestRateReceived;   //  interest rate set by B for creditline given from B to A

        uint16 feesOutstandingA;       //  fees outstanding by A
        uint16 feesOutstandingB;       //  fees outstanding by B

        uint16 mtime;                  //  last modification time

        int64 balance;                 //  balance between A and B, A->B (x(-1) for B->A)
    }

    struct TrustlineRequest {
        uint32 creditlineGiven;
        uint32 creditlineReceived;
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
     */
    function init(
        string _name,
        string _symbol,
        uint8 _decimals,
        uint16 _capacityImbalanceFeeDivisor
    )
        onlyOwner
        external
    {
        require(_decimals < 10);
        name = _name;
        symbol = _symbol;
        decimals = _decimals;
        capacityImbalanceFeeDivisor = _capacityImbalanceFeeDivisor;
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
        uint32 _value,
        uint32 _maxFee,
        address[] _path
    )
        external
        returns (bool _success)
    {
        return _mediatedTransfer(
            msg.sender,
            _to,
            _value,
            _maxFee,
            _path);
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
        uint32 _value,
        uint32 _maxFee,
        address[] _path
    )
        external
        returns (bool success)
    {
        require(authorized[msg.sender]);
        return _mediatedTransfer(
            _from,
            _to,
            _value,
            _maxFee,
            _path);
    }

    /**
     * @notice `msg.sender` offers a creditline to `_debtor` of `_value` tokens, must be accepted by debtor
     * @param _debtor The account that can spend tokens up to the given amount
     * @param _value The maximum amount of tokens that can be spend
     */
    function updateCreditline(address _debtor, uint32 _value) external notSender(_debtor) returns (bool _success) {
        address creditor = msg.sender;
        if (_value < creditline(creditor, _debtor)) {
            _updateCreditline(creditor, _debtor, _value);
        } else {
            bytes32 id = acceptId(creditor, _debtor);
            requestedCreditlineUpdates[id] = _value;
            emit CreditlineUpdateRequest(creditor, _debtor, _value);
        }
        _success = true;
    }

    /**
     * @notice `msg.sender` accepts a creditline offered before from `_creditor` of `_value` tokens
     * @param _creditor The account that spends tokens up to the given amount
     * @param _value The maximum amount of tokens that can be spend
     * @return true, if the credit was successful
     */
    function acceptCreditline(address _creditor, uint32 _value) external returns (bool _success) {
        address debtor = msg.sender;
        // retrieve acceptId to validate that updateCreditline has been called
        bytes32 id = acceptId(_creditor, debtor);
        require(requestedCreditlineUpdates[id] == _value);
        delete requestedCreditlineUpdates[id];
        _updateCreditline(_creditor, debtor, _value);
        _success = true;
    }

    /**
     * @notice `msg.sender` offers a trustline update to `_debtor` of `_creditlineGiven` tokens for `_creditlineReceived` token
     * Needs to be accepted by the other party
     * @param _debtor The other party of the trustline agreement
     * @param _creditlineGiven The creditline limit given by msg.sender
     * @param _creditlineReceived The creditline limit given _debtor
     * @return true, if the credit was successful
     */
    function updateTrustline(address _debtor, uint32 _creditlineGiven, uint32 _creditlineReceived) external returns (bool _success) {
        return _updateTrustline(
            msg.sender,
            _debtor,
            _creditlineGiven,
            _creditlineReceived);
    }

    /**
     * @notice `msg.sender` reduces a creditline from `_creditor` to `_value` tokens
     * @param _creditor The account the creditline was given from
     * @param _value The new maximum amount of tokens that can be spend, must be smaller than the old one
     * @return true, if the creditline update was successful
     */
    function reduceCreditline(address _creditor, uint32 _value) external returns (bool _success) {
        address debtor = msg.sender;
        require(_value < creditline(_creditor, debtor));
        _updateCreditline(_creditor, debtor, _value);
        _success = true;
    }

    /**
     * @dev The ERC20 Token balance for the spender. This is different from the balance within a trustline.
     *      In Trustlines this is the spendable amount
     * @param _owner The address from which the balance will be retrieved
     * @return The balance
     */
    function balanceOf(address _owner) external constant returns (uint256) {
        return spendable(_owner);
    }

    /**
     * @return total amount of tokens. In Trustlines this is the sum of all creditlines
     */
    function totalSupply() external constant returns (uint256 supply) {
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
    function getAccount(address _a, address _b) external constant returns (int, int, int, int, int, int, int, int) {
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
        uint32 _creditlineGiven,
        uint32 _creditlineReceived,
        uint16 _interestRateGiven,
        uint16 _interestRateReceived,
        uint16 _feesOutstandingA,
        uint16 _feesOutstandingB,
        uint16 _mtime,
        int64 _balance
    )
        onlyOwner
        external
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
        int64 balance = account.balance;
        uint32 creditline = account.creditlineReceived;
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

    function calculateMtime() public constant returns (uint16 mtime) {
        mtime = uint16((now / (24 * 60 * 60)) - ((2017 - 1970) * 365));
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

    function _directTransfer(
        address _sender,
        address _receiver,
        uint32 _value
    )
        internal
        returns (uint32 fees)
    {
        Account memory account = _loadAccount(_sender, _receiver);

        uint32 creditlineReceived = account.creditlineReceived;
        fees = _calculateFees(_value, account.balance, capacityImbalanceFeeDivisor);
        int64 newBalance = account.balance - _value - fees;

        // check if creditline is not exceeded
        require(-newBalance <= creditlineReceived);
        account.balance = newBalance;

        // store new balance
        _storeAccount(_sender, _receiver, account);
        // Should be removed later
        emit BalanceUpdate(_sender, _receiver, newBalance);
    }

    function _mediatedTransfer(
        address _from,
        address _to,
        uint32 _value,
        uint32 _maxFee,
        address[] _path
    )
        internal
        returns (bool success)
    {
        // check Path: is there a Path and is _to the last address? Otherwise throw
        require((_path.length > 0) && (_to == _path[_path.length - 1]));

        uint32 forwardedValue = _value;
        uint32 fees = 0;
        uint32 fee = 0;

        // check path in reverse to correctly accumulate the fee
        for (uint i = _path.length; i > 0; i--) {
            address receiver = _path[i-1];
            address sender;
            if (i == 1) {
                sender = _from;
            } else {
                sender = _path[i-2];
            }
            fee = _directTransfer(
                sender,
                receiver,
                forwardedValue);
            // forward the value + the fee
            forwardedValue += fee;
            fees += fee;
            require(fees <= _maxFee);
        }

        emit Transfer(
            _from,
            _to,
            _value);

        success = true;
    }

    function addToUsersAndFriends(address _a, address _b) internal {
        users.insert(_a);
        users.insert(_b);
        friends[_a].insert(_b);
        friends[_b].insert(_a);
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
            result.balance = -account.balance;
        }
        return result;
    }

    function _storeAccount(address _a, address _b, Account account) internal {
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
        TrustlineRequest storage trustlineRequest = requestedTrustlineUpdates[uniqueIdentifier(_a, _b)];
        trustlineRequest.creditlineGiven = _trustlineRequest.creditlineGiven;
        trustlineRequest.creditlineReceived = _trustlineRequest.creditlineReceived;
        trustlineRequest.initiator = _trustlineRequest.initiator;
    }

    function _updateCreditline(address _creditor, address _debtor, uint32 _value) internal returns (bool success) {
        Account memory account = _loadAccount(_creditor, _debtor);

        addToUsersAndFriends(_creditor, _debtor);
        account.creditlineGiven = _value;

        _storeAccount(_creditor, _debtor, account);
        emit CreditlineUpdate(_creditor, _debtor, _value);
        success = true;
    }

    function _updateTrustline(
        address _creditor,
        address _debtor,
        uint32 _creditlineGiven,
        uint32 _creditlineReceived
    )
        internal
        returns (bool success)
    {
        Account memory account = _loadAccount(_creditor, _debtor);

        // reduce of creditline is always possible
        if (_creditlineGiven <= account.creditlineGiven && _creditlineReceived <= account.creditlineReceived) {
            _setTrustline(
                _creditor,
                _debtor,
                _creditlineGiven,
                _creditlineReceived);
            return true;
        }

        TrustlineRequest memory trustlineRequest = _loadTrustlineRequest(_creditor, _debtor);

        // if original initiator is debtor, try to accept request
        if (trustlineRequest.initiator == _debtor) {
            if (trustlineRequest.creditlineGiven == _creditlineReceived &&
                trustlineRequest.creditlineReceived == _creditlineGiven) {

                _setTrustline(
                    trustlineRequest.initiator,
                    _creditor,
                    trustlineRequest.creditlineGiven,
                    trustlineRequest.creditlineReceived
                );

                return true;
            } else {
                _requestTrustlineUpdate(
                    _creditor,
                    _debtor,
                    _creditlineGiven,
                    _creditlineReceived
                );

                return true;
            }
        // update the trustline request
        } else {
            _requestTrustlineUpdate(
                _creditor,
                _debtor,
                _creditlineGiven,
                _creditlineReceived
            );

            return true;
        }
    }

    function _setTrustline(
        address _creditor,
        address _debtor,
        uint32 _creditlineGiven,
        uint32 _creditlineReceived
    )
        internal
    {
        Account memory _account = _loadAccount(_creditor, _debtor);
        addToUsersAndFriends(_creditor, _debtor);
        _account.creditlineGiven = _creditlineGiven;
        _account.creditlineReceived = _creditlineReceived;
        _storeAccount(_creditor, _debtor, _account);

        emit TrustlineUpdate(
            _creditor,
            _debtor,
            _creditlineGiven,
            _creditlineReceived
        );
    }

    function _requestTrustlineUpdate(
        address _creditor,
        address _debtor,
        uint32 _creditlineGiven,
        uint32 _creditlineReceived
    )
        internal
    {
        _storeTrustlineRequest(
            _creditor,
            _debtor,
            TrustlineRequest(_creditlineGiven, _creditlineReceived, _creditor)
        );

        emit TrustlineUpdateRequest(
            _creditor,
            _debtor,
            _creditlineGiven,
            _creditlineReceived
        );
    }

    function _calculateFees(uint32 _value, int64 _balance, uint16 _capacityImbalanceFeeDivisor) internal pure returns (uint32) {
        if (_capacityImbalanceFeeDivisor == 0) {
            return 0;
        }

        int64 imbalanceGenerated = int64(_value);
        if (_balance > 0) {
            imbalanceGenerated = _value - _balance;
            if (imbalanceGenerated <= 0) {
                return 0;
            }
        }
        return uint32(uint32(imbalanceGenerated / _capacityImbalanceFeeDivisor) + 1);  // minimum fee is 1
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

    function _abs(int64 _balance) internal pure returns (int64 _absBalance) {
        if (_balance < 0) {
            _absBalance = - _balance;
        } else {
            _absBalance = _balance;
        }
    }

}
