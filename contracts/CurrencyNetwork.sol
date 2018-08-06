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

    // interests settings, interests are expressed in 0.001% per year
    int16 public defaultInterests;
    bool public customInterests;
    bool public safeInterestRippling;

    // Events
    event Transfer(address indexed _from, address indexed _to, uint _value);
    event TrustlineUpdateRequest(address indexed _creditor, address indexed _debtor, uint _creditlineGiven, uint _creditlineReceived, int _interestRateGiven, int _interestRateReceived);
    event TrustlineUpdate(address indexed _creditor, address indexed _debtor, uint _creditlineGiven, uint _creditlineReceived, int _interestRateGiven, int _interestRateReceived);

    event BalanceUpdate(address indexed _from, address indexed _to, int256 _value);

    // for accounting balance and trustline between two users introducing fees and interests
    // currently uses 256 + 232 bits, 24 remaining to make two structs
    struct Account {
        // A < B (A is the lower address)

        uint128 creditlineGiven;        //  creditline given by A to B, always positive
        uint128 creditlineReceived;     //  creditline given by B to A, always positive

        int16 interestRateGiven;      //  interest rate set by A for creditline given by A to B in 0.001% per year
        int16 interestRateReceived;   //  interest rate set by B for creditline given from B to A in 0.001% per year

        uint16 feesOutstandingA;       //  fees outstanding by A
        uint16 feesOutstandingB;       //  fees outstanding by B

        uint32 mtime;                  //  last modification time

        int136 balance;                 //  balance between A and B, A->B (x(-1) for B->A)
    }

    struct TrustlineRequest {
        uint128 creditlineGiven;
        uint128 creditlineReceived;
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
     * @param _defaultInterests The default interests for every trustlines in 0.001% per year
     * @param _customInterests Flag to allow or disallow trustlines to have custom interests
     * @param _safeInterestRippling Flag to allow or disallow transactions resulting in loss of interests for intermediaries, unless the transaction exclusively reduces balances
     */
    function init(
        string _name,
        string _symbol,
        uint8 _decimals,
        uint16 _capacityImbalanceFeeDivisor,
        int16 _defaultInterests,
        bool _customInterests,
        bool _safeInterestRippling
    )
        onlyOwner
        external
    {
        require(_decimals < 19);
        // verifies that one parameter is selected.
        require(! ((_defaultInterests > 0) && _customInterests));
        require(!_safeInterestRippling || (_safeInterestRippling && _customInterests));

        name = _name;
        symbol = _symbol;
        decimals = _decimals;
        capacityImbalanceFeeDivisor = _capacityImbalanceFeeDivisor;
        defaultInterests = _defaultInterests;
        customInterests = _customInterests;
        safeInterestRippling = _safeInterestRippling;
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
        uint128 _value,
        uint128 _maxFee,
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
        uint128 _value,
        uint128 _maxFee,
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
     * @notice `msg.sender` offers a trustline update to `_debtor` of `_creditlineGiven` tokens for `_creditlineReceived` token
     * Needs to be accepted by the other party, unless we reduce both values.
     * @param _debtor The other party of the trustline agreement
     * @param _creditlineGiven The creditline limit given by msg.sender
     * @param _creditlineReceived The creditline limit given _debtor
     * @param _interestRateGiven The interest given by msg.sender
     * @param _interestRateReceived The interest given by _debtor
     * @return true, if the credit was successful
     */
    function updateTrustline(address _debtor, uint128 _creditlineGiven, uint128 _creditlineReceived, int16 _interestRateGiven, int16 _interestRateReceived) external returns (bool _success) {
        require(customInterests || (_interestRateGiven == defaultInterests && _interestRateReceived == defaultInterests));

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
     * @notice `msg.sender` offers a trustline update to `_debtor` of `_creditlineGiven` tokens for `_creditlineReceived` token with default interests
     * Needs to be accepted by the other party, unless we reduce both values.
     * @param _debtor The other party of the trustline agreement
     * @param _creditlineGiven The creditline limit given by msg.sender
     * @param _creditlineReceived The creditline limit given _debtor
     * @return true, if the credit was successful
     */
    function updateTrustlineDefaultInterests(address _debtor, uint128 _creditlineGiven, uint128 _creditlineReceived) external returns (bool _success) {
        address _creditor = msg.sender;

        return _updateTrustline(
            _creditor,
            _debtor,
            _creditlineGiven,
            _creditlineReceived,
            defaultInterests,
            defaultInterests
        );
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
        uint128 _creditlineGiven,
        uint128 _creditlineReceived,
        int16 _interestRateGiven,
        int16 _interestRateReceived,
        uint16 _feesOutstandingA,
        uint16 _feesOutstandingB,
        uint32 _mtime,
        int136 _balance
    )
        onlyOwner
        external
    {
        require(customInterests || (_interestRateGiven == defaultInterests && _interestRateReceived == defaultInterests));

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
        uint128 _creditlineGiven,
        uint128 _creditlineReceived,
        uint16 _feesOutstandingA,
        uint16 _feesOutstandingB,
        uint32 _mtime,
        int136 _balance
    )
        onlyOwner
        external
    {
        _setAccount(
            _a,
            _b,
            _creditlineGiven,
            _creditlineReceived,
            defaultInterests,
            defaultInterests,
            _feesOutstandingA,
            _feesOutstandingB,
            _mtime,
            _balance
        );
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
        int136 balance = account.balance;
        uint128 creditline = account.creditlineReceived;
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

    function _directTransfer(
        address _sender,
        address _receiver,
        uint128 _value
    )
        internal
        returns (uint128 fees)
    {
        Account memory account = _loadAccount(_sender, _receiver);

        uint32 mtime = account.mtime;
        int136 interests = _calculateInterests(account.balance, mtime, account.interestRateGiven, account.interestRateReceived);
        int136 newBalance = account.balance + interests;

        fees = _calculateFees(_value, newBalance, capacityImbalanceFeeDivisor);
        newBalance = newBalance - _value - fees;

        // check if creditline is not exceeded
        uint128 creditlineReceived = account.creditlineReceived;
        require(-newBalance <= int136(creditlineReceived));
        account.balance = newBalance;
        account.mtime = uint32(now);

        // store new balance
        _storeAccount(_sender, _receiver, account);
        // Should be removed later
        emit BalanceUpdate(_sender, _receiver, newBalance);
    }

    function _mediatedTransfer(
        address _from,
        address _to,
        uint128 _value,
        uint128 _maxFee,
        address[] _path
    )
        internal
        returns (bool success)
    {
        // check Path: is there a Path and is _to the last address? Otherwise throw
        require((_path.length > 0) && (_to == _path[_path.length - 1]));

        uint128 forwardedValue = _value;
        uint128 fees = 0;
        uint128 fee = 0;
        int136 previousInterestsWeight = 0;

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

            if (safeInterestRippling) {
                // we want to prevent intermediaries to pay more interests than they receive
                // If the transaction does not result in them paying interests but getting paid less interests then transaction is valid
                // i.e. transaction is valid if the receiver still owes the sender after transfer
                Account memory account = _loadAccount(sender, receiver);
                int136 nextInterestsWeight = _calculateInterestWeight(sender, receiver, forwardedValue);

                require(nextInterestsWeight <= previousInterestsWeight || account.balance - forwardedValue >= 0);

                previousInterestsWeight = nextInterestsWeight;
            }
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

    function _setAccount(
        address _a,
        address _b,
        uint128 _creditlineGiven,
        uint128 _creditlineReceived,
        int16 _interestRateGiven,
        int16 _interestRateReceived,
        uint16 _feesOutstandingA,
        uint16 _feesOutstandingB,
        uint32 _mtime,
        int136 _balance
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
        Account storage acc = accounts[uniqueIdentifier(_a, _b)];
        if (_a < _b) {
            acc.creditlineGiven = account.creditlineGiven;
            acc.creditlineReceived = account.creditlineReceived;
            if (! customInterests) {
                acc.interestRateGiven = defaultInterests;
                acc.interestRateReceived = defaultInterests;
            } else {
                acc.interestRateGiven = account.interestRateGiven;
                acc.interestRateReceived = account.interestRateReceived;
            }
            acc.feesOutstandingA = account.feesOutstandingA;
            acc.feesOutstandingB = account.feesOutstandingB;
            acc.mtime = account.mtime;
            acc.balance = account.balance;
        } else {
            acc.creditlineReceived = account.creditlineGiven;
            acc.creditlineGiven = account.creditlineReceived;
            if (!customInterests) {
                acc.interestRateGiven = defaultInterests;
                acc.interestRateReceived = defaultInterests;
            } else {
                acc.interestRateReceived = account.interestRateGiven;
                acc.interestRateGiven = account.interestRateReceived;
            }
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
        if (!customInterests) {
            trustlineRequest.interestRateGiven = defaultInterests;
            trustlineRequest.interestRateReceived = defaultInterests;
        } else {
            trustlineRequest.interestRateGiven = _trustlineRequest.interestRateGiven;
            trustlineRequest.interestRateReceived = _trustlineRequest.interestRateReceived;
        }
        trustlineRequest.initiator = _trustlineRequest.initiator;
    }

    // in this function, it is assumed _creditor is the initator of the trustline update (see _requestTrustlineUpdate())
    function _updateTrustline(
        address _creditor,
        address _debtor,
        uint128 _creditlineGiven,
        uint128 _creditlineReceived,
        int16 _interestRateGiven,
        int16 _interestRateReceived
    )
        internal
        returns (bool success)
    {
        Account memory account = _loadAccount(_creditor, _debtor);

        // reduce of creditlines and interests is always possible
        if (_creditlineGiven <= account.creditlineGiven && _creditlineReceived <= account.creditlineReceived && _interestRateGiven == account.interestRateGiven && _interestRateReceived == account.interestRateReceived) {
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
            if (_creditlineReceived <= trustlineRequest.creditlineGiven && _creditlineGiven <= trustlineRequest.creditlineReceived && _interestRateReceived == trustlineRequest.interestRateGiven && _interestRateGiven == trustlineRequest.interestRateReceived) {

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

    function _setTrustline(
        address _creditor,
        address _debtor,
        uint128 _creditlineGiven,
        uint128 _creditlineReceived,
        int16 _interestRateGiven,
        int16 _interestRateReceived
    )
        internal
    {
        Account memory _account = _loadAccount(_creditor, _debtor);
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
        uint128 _creditlineGiven,
        uint128 _creditlineReceived,
        int16 _interestRateGiven,
        int16 _interestRateReceived
    )
        internal
    {
        _storeTrustlineRequest(
            _creditor,
            _debtor,
            TrustlineRequest(_creditlineGiven, _creditlineReceived, _interestRateGiven, _interestRateReceived, _creditor)
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

    function _calculateFees(uint128 _value, int136 _balance, uint16 _capacityImbalanceFeeDivisor) internal pure returns (uint128) {
        if (_capacityImbalanceFeeDivisor == 0) {
            return 0;
        }

        int136 imbalanceGenerated = int136(_value);
        if (_balance > 0) {
            imbalanceGenerated = _value - _balance;
            if (imbalanceGenerated <= 0) {
                return 0;
            }
        }
        return uint128(uint128(imbalanceGenerated / _capacityImbalanceFeeDivisor) + 1);  // minimum fee is 1
    }

    function _calculateInterests(int136 _balance, uint32 _mtime, int16 _interestRateGiven, int16 _interestRateReceived) internal view returns (int136) {
        int16 rate = defaultInterests;

        if (customInterests) {
            if (_balance > 0) {
                rate = _interestRateGiven;
            }else {
                rate = _interestRateReceived;
            }
        }

        return int136(_balance * int136(now - _mtime)/(60*60*24*365) * int136(rate)/100000);
    }

    // Calculates a representation of how much interests intermediaries (_b) gain participating in a transfer
    // It is only calculating for one side and does not take into accounts the gains or loss from the whole mediation.
    function _calculateInterestWeight(address _a, address _b, uint128 _transfer) internal view returns (int136) {

        Account memory account = _loadAccount(_a, _b);

        int136 transfer = int136(_transfer);

        if (transfer <= _abs(account.balance) || account.balance <= 0) {
            // this means the_transfer will impact only one interest rate
            if (account.balance > 0) {
                // _b owes to _a; the interests rate to take into account are interests rate given by _a
                return transfer * account.interestRateGiven;
            } else {
                // _a owes to _b; the interests rate to take into account are interests rate received by _a
                // _b is actually losing, so the value is negative (for a positive interest rate)
                return - transfer * account.interestRateReceived;
            }

        } else {
            int136 remainingTransfer = transfer - _abs(account.balance);
            if (account.balance > 0) {
                return account.balance * account.interestRateGiven + remainingTransfer * account.interestRateReceived;
            } else {
                return account.balance * account.interestRateReceived + remainingTransfer * account.interestRateGiven;
            }
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

    function _abs(int136 _balance) internal pure returns (int136 _absBalance) {
        if (_balance < 0) {
            _absBalance = - _balance;
        } else {
            _absBalance = _balance;
        }
    }

}
