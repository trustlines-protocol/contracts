pragma solidity ^0.4.11;


import "./lib/it_set_lib.sol";  // Library for Set iteration
import "./lib/ECVerify.sol";  // Library for safer ECRecovery
import "./lib/Receiver_Interface.sol";  // Library for Token Receiver ERC223 Interface
import "./lib/ERC223_Interface.sol";  // Library for Token ERC223 Interface
import "./CurrencyNetworkInterface.sol";  // Interface for a currency Network


/*
 * CurrencyNetwork
 *
 * Main contract of Trustlines, encapsulates all creditlines and trustlines.
 * Implements ERC20 token interface and functionality, adds fees on different levels.
 *
 * Note: use of CurrentNetworkFactory is highly recommended.
 */
contract CurrencyNetwork {

    using ItSet for ItSet.AddressSet;
    mapping (bytes32 => Account) internal accounts;
    // mapping (acceptId) => timestamp
    mapping (bytes32 => uint16) internal proposedCreditlineUpdates;
    // mapping (chequeId) => timestamp
    mapping (bytes32 => uint16) internal cheques;

    // TODO: this should be removed later, but currently it is used by the relay server
    // friends, users address has an account with
    mapping (address => ItSet.AddressSet) internal friends;
    //list of all users of the system
    ItSet.AddressSet internal users;

    // Divides current value being transferred to calculate the capacity fee which equals the imbalance fee
    uint16 internal capacityImbalanceFeeDivisor;
    uint16 internal networkFeeDivisor;

    // meta data for token part
    string public name;
    string public symbol;
    uint8 public decimals;

    // Events
    event Transfer(address indexed _from, address indexed _to, uint _value, bytes _data);
    event CreditlineUpdateRequest(address indexed _creditor, address indexed _debtor, uint _value);
    event CreditlineUpdate(address indexed _creditor, address indexed _debtor, uint _value);
    event ChequeCashed(address indexed _from, address indexed _to, uint32 _value, bytes32 _id);
    // TODO: remove this due to gas costs, currently used by relay server
    event BalanceUpdate(address indexed _from, address indexed _to, int256 _value);

    // for accounting balance and trustline between two users introducing fees and interests
    // currently uses 208 bits, 48 remaining
    struct Account {
        // A < B (A is the lower address)

        uint32 creditlineAB;        //  creditline given by A to B, always positive
        uint32 creditlineBA;        //  creditline given by B to A, always positive

        uint16 interestAB;          //  interest rate set by A for debt of B
        uint16 interestBA;          //  interest rate set by B for debt of A

        uint16 feesOutstandingA;    //  fees outstanding by A
        uint16 feesOutstandingB;    //  fees outstanding by B

        uint16 mtime;               //  last modification time

        int64 balanceAB;            //  balance between A and B, A->B (x(-1) for B->A)
    }

    modifier notSender(address _sender) {
        require(_sender != msg.sender);
        _;
    }

    // check value is inbounds for accounting to prevent overflows
    modifier valueWithinInt32(uint _value)
    {
        require(_value < 2 ** 32);
        _;
    }

    function CurrencyNetwork() public {
        // don't do anything here due to upgradeability issues (no contructor-call on replacement).
    }

    /*
     * @notice initialize the contract
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @param _maxFee Maximum for fee which occurs when the path is used for transfer
     * @param _path Path of Trustlines calculated by external service (relay server)
     */
    function init(
        string _tokenName,
        string _tokenSymbol,
        uint8 _decimals,
        uint16 _networkFeeDivisor,
        uint16 _capacityImbalanceFeeDivisor
    )
        //TODO add modifier to restrict access
        public
    {
        require(_decimals < 10);
        name = _tokenName;
        symbol = _tokenSymbol;
        decimals = _decimals;
        networkFeeDivisor = _networkFeeDivisor;
        capacityImbalanceFeeDivisor = _capacityImbalanceFeeDivisor;
    }

    /*
     * @notice cashCheque required a signature which must be provided by the UI
     * @param _from The address of the account able to transfer the tokens
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @param _expiresOn Days till the cheque expires
     * @param _signature the values _from, _to, _value and _expiresOn signed by _from
     * @return true, if there was no error in transfer
     */
    function cashCheque(
        address _from,
        address _to,
        uint32 _value,
        uint16 _maxFee,
        uint16 _expiresOn,
        uint _nounce,
        address[] _path,
        bytes _signature
    )
        external
        returns (bool success)
    {
        bytes32 id = chequeId(
            _from,
            _to,
            _value,
            _maxFee,
            _expiresOn,
            _nounce);
        address signer = ECVerify.ecverify(id, _signature);
        require(signer == _from);

        // was it not cashed yet
        require(cheques[id] == 0);

        uint16 mtime = calculateMtime();
        // is it still valid
        require(_expiresOn >= mtime);

        _mediatedTransfer(
            _from,
            _to,
            _value,
            _maxFee,
            _path);

        // set to cashed
        cheques[id] = mtime;

        ChequeCashed(
            _from,
            _to,
            _value,
            id);
        success = true;
    }

    /*
     * @notice send `_value` token to `_to` from `msg.sender`, the path must have been prepared with function `prepare` first
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @param _maxFee Maximum fee the sender wants to pay
     * @param _path Path between msg.sender and _to
     */
    function transfer(
        address _to,
        uint32 _value,
        uint16 _maxFee,
        address[] _path
    )
        external
        returns (bool _success)
    {
        return _mediatedTransfer(
            msg.sender,
            _to, _value,
            _maxFee,
            _path);
    }

    /*
     * @notice `msg.sender` gives a creditline to `_debtor` of `_value` tokens, must be accepted by debtor
     * @param _debtor The account that can spend tokens up to the given amount
     * @param _value The maximum amount of tokens that can be spend
     */
    function updateCreditline(address _debtor, uint32 _value) external notSender(_debtor) returns (bool _success) {
        address creditor = msg.sender;
        if (_value < creditline(creditor, _debtor)) {
            _updateCreditline(creditor, _debtor, _value);
        } else {
            bytes32 id = acceptId(creditor, _debtor, _value);
            // currently storing the time of request to be able to remove too old ones later
            proposedCreditlineUpdates[id] = calculateMtime();
            CreditlineUpdateRequest(creditor, _debtor, _value);
        }
        _success = true;
    }

    /*
     * @notice `msg.sender` accepts a creditline from `_creditor` of `_value` tokens
     * @param _creditor The account that spends tokens up to the given amount
     * @param _value The maximum amount of tokens that can be spend
     * @return true, if the credit was successful
     */
    function acceptCreditline(address _creditor, uint32 _value) external returns (bool _success) {
        address debtor = msg.sender;
        // retrieve acceptId to validate that updateCreditline has been called
        bytes32 id = acceptId(_creditor, debtor, _value);
        require(proposedCreditlineUpdates[id] > 0);
        //doesnt work with testrpc, should delete the update request
        delete proposedCreditlineUpdates[id];
        _updateCreditline(_creditor, debtor, _value);
        _success = true;
    }

    /*
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

    /*
     * @dev The ERC20 Token balance for the spender. This is different from the balance within a trustline.
     *      In Trustlines this is the spendable amount
     * @param _owner The address from which the balance will be retrieved
     * @return The balance
     */
    function balanceOf(address _owner) external constant returns (uint256) {
        return spendable(_owner);
    }

    /*
     * @return total amount of tokens. In Trustlines this is the sum of all creditlines
     */
    function totalSupply() external constant returns (uint256 supply) {
        supply = 0;
        var userList = users.list;
        for (uint i = 0; i < userList.length; i++) {
            supply += spendable(userList[i]);
        }
    }

    function getAccount(address _A, address _B) external constant returns (int, int, int, int, int, int, int, int) {
        Account memory account = _loadAccount(_A, _B);

        return (
            account.creditlineAB,
            account.creditlineBA,
            account.interestAB,
            account.interestBA,
            account.feesOutstandingA,
            account.feesOutstandingB,
            account.mtime,
            account.balanceAB);
    }

    function getAccountLen() external constant returns (uint) {
        return 8 * 32 + 2;
    }

    function setAccount(
        address _A,
        address _B,
        uint32 _creditlineAB,
        uint32 _creditlineBA,
        uint16 _interestAB,
        uint16 _interestBA,
        uint16 _feesOutstandingA,
        uint16 _feesOutstandingB,
        uint16 _mtime,
        int64 _balanceAB
    )
        /*TODO modifier to restrict access */
        external
    {
        Account memory account;

        account.creditlineAB = _creditlineAB;
        account.creditlineBA = _creditlineBA;
        account.interestAB = _interestAB;
        account.interestBA = _interestBA;
        account.feesOutstandingA = _feesOutstandingA;
        account.feesOutstandingB = _feesOutstandingB;
        account.mtime = _mtime;
        account.balanceAB = _balanceAB;

        _storeAccount(_A, _B, account);

        addToUsersAndFriends(_A, _B);
    }

    /*
     * @notice Gets the sum of system fees as applicable when A sends B and transfer
     * @dev Gets the sum of system fees as applicable when A sends B and transfer
     * @param Ethereum Addresses of A and B
     */
    function getFeesOutstanding(address _A, address _B) external constant returns (int fees) {
        Account memory account = _loadAccount(_A, _B);
        fees = account.feesOutstandingA;
    }

    /*
     * @notice Checks for the spendable amount by spender
     * @param _spender The address from which the balance will be retrieved
     * @return spendable The spendable amount
     */
    function spendable(address _spender) public constant returns (uint _spendable) {
        _spendable = 0;
        var myfriends = friends[_spender].list;
        for (uint i = 0; i < myfriends.length; i++) {
            _spendable += spendableTo(_spender, myfriends[i]);
        }
    }

    /*
     * @notice the maximum spendable amount by the spender to the receiver.
     * @param _spender The account spending the tokens
     * @param _receiver the receiver that receives the tokens
     * @return Amount of remaining tokens allowed to spend
     */
    function spendableTo(address _spender, address _receiver) public constant returns (uint remaining) {
        Account memory account = _loadAccount(_spender, _receiver);
        int64 balance = account.balanceAB;
        uint32 creditline = account.creditlineBA;
        remaining = uint(creditline + balance);
    }

    // PUBLIC GETTERS

    /*
     * @param _owner The address of the account owning tokens
     * @param _spender The address of the account able to transfer the tokens
     * @return Amount tokens allowed to spent
     */
    function creditline(address _creditor, address _debtor) public constant returns (uint _creditline) {
        // returns the current creditline given by A to B
        Account memory account = _loadAccount(_creditor, _debtor);
        _creditline = account.creditlineAB;
    }

    /*
     * @notice returns what B owes to A
     * @dev If negative A owes B, if positive B owes A
     * @param Ethereum addresses A and B which have trustline relationship established between them
     */
    function balance(address _A, address _B) public constant returns (int _balance) {
        Account memory account = _loadAccount(_A, _B);
        _balance = account.balanceAB;
    }

    /*
     * @notice gets friends of user
     * @param Ethereum Address of the user
     */
    function getFriends(address _user) public constant returns (address[]) {
        return friends[_user].list;
    }

    function getFriendsReturnSize(address _user) public constant returns (uint) {
        return getFriends(_user).length + 2;
    }

    /*
     * @notice gets friends of user
     * @param Ethereum Address of the user
     */

    function getUsers() public constant returns (address[]) {
        return users.list;
    }

    function getUsersReturnSize() public constant returns (uint) {
        // Returning a dynamically-sized array requires two extra slots.
        // One for the data location pointer, and one for the length.
        return getUsers().length + 2;
    }

    /*
     * @notice Calculates the current modification day since system start.
     * @notice now is an alias for block.timestamp gives the epoch time of the current block.
     */
    function calculateMtime() public constant returns (uint16 mtime) {
        mtime = uint16((now / (24 * 60 * 60)) - ((2017 - 1970) * 365));
    }

    function _directTransfer(
        address _sender,
        address _receiver,
        uint32 _value,
        uint _hopNumber
    )
        internal
    {
        Account memory accountReceiverSender = _loadAccount(_receiver, _sender);

        if (_hopNumber == 0) {
            uint16 fees = _calculateNetworkFee(_value, networkFeeDivisor);
            accountReceiverSender.feesOutstandingA += fees;
        }

        int64 balanceAB = accountReceiverSender.balanceAB;

        // check Creditlines (value + balance must not exceed creditline)
        uint32 creditlineAB = accountReceiverSender.creditlineAB;
        uint32 nValue = _value - _calculateFees(_value, balanceAB, capacityImbalanceFeeDivisor);

        require(nValue + balanceAB <= creditlineAB);

        // apply Interests
        uint16 elapsed = calculateMtime() - accountReceiverSender.mtime;
        int64 interest = _occurredInterest(accountReceiverSender.balanceAB, accountReceiverSender.interestAB, elapsed);
        accountReceiverSender.balanceAB += interest;

        // store new balance
        accountReceiverSender.balanceAB = nValue + balanceAB;
        _storeAccount(_receiver, _sender, accountReceiverSender);

        // Should be removed later
        BalanceUpdate(_receiver, _sender, accountReceiverSender.balanceAB);
    }

    function _mediatedTransfer(
        address _from,
        address _to,
        uint32 _value,
        uint16 _maxFee,
        address[] _path
    )
        internal
        returns (bool success)
    {
        // check Path: is there a Path and is _to the last address? Otherwise throw
        require((_path.length > 0) && (_to == _path[_path.length - 1]));

        // calculate inverse and set as real value
        int32 rValue = int32(_value);
        //uint16 fees = 0; // TODO

        for (uint i = _path.length; i > 0; i--) {
            address receiver = _path[i-1];
            address sender;
            if (i == 1) {
                sender = _from;
            } else {
                sender = _path[i-2];
            }
            _directTransfer(
                sender,
                receiver,
                uint32(rValue),
                i);
        }
        bytes memory empty;

        Transfer(
            _from,
            _to,
            _value,
            empty);

        // For ERC223, callback to receiver if it is contract
        if (isContract(_to)) {
            ContractReceiver contractReceiver = ContractReceiver(_to);

            contractReceiver.tokenFallback(_to, _value, empty);
        }
        success = true;
    }

    function addToUsersAndFriends(address _A, address _B) internal {
        users.insert(_A);
        users.insert(_B);
        friends[_A].insert(_B);
        friends[_B].insert(_A);
    }

    function _loadAccount(address _A, address _B) internal constant returns (Account) {
        Account memory account = accounts[uniqueIdentifier(_A, _B)];
        Account memory result;
        if (_A < _B) {
            result = account;
        } else {
            result.creditlineBA = account.creditlineAB;
            result.creditlineAB = account.creditlineBA;
            result.interestBA = account.interestAB;
            result.interestAB = account.interestBA;
            result.feesOutstandingB = account.feesOutstandingA;
            result.feesOutstandingA = account.feesOutstandingB;
            result.mtime = account.mtime;
            result.balanceAB = -account.balanceAB;
        }
        return result;
    }

    function _storeAccount(address _A, address _B, Account account) internal {
        Account storage acc = accounts[uniqueIdentifier(_A, _B)];
        if (_A < _B) {
            acc.creditlineAB = account.creditlineAB;
            acc.creditlineBA = account.creditlineBA;
            acc.interestAB = account.interestAB;
            acc.interestBA = account.interestBA;
            acc.feesOutstandingA = account.feesOutstandingA;
            acc.feesOutstandingB = account.feesOutstandingB;
            acc.mtime = account.mtime;
            acc.balanceAB = account.balanceAB;
        } else {
            acc.creditlineBA = account.creditlineAB;
            acc.creditlineAB = account.creditlineBA;
            acc.interestBA = account.interestAB;
            acc.interestAB = account.interestBA;
            acc.feesOutstandingB = account.feesOutstandingA;
            acc.feesOutstandingA = account.feesOutstandingB;
            acc.mtime = account.mtime;
            acc.balanceAB = - account.balanceAB;
        }
    }

    function _updateCreditline(address _creditor, address _debtor, uint32 _value) internal returns (bool success) {
        Account memory account = _loadAccount(_creditor, _debtor);

        addToUsersAndFriends(_creditor, _debtor);
        account.creditlineAB = _value;

        _storeAccount(_creditor, _debtor, account);
        CreditlineUpdate(_creditor, _debtor, _value);
        success = true;
    }

    function _calculateNetworkFee(uint32 _value, uint16 _networkFeeDivisor) internal pure returns (uint16) {
        if (_networkFeeDivisor == 0) {
            return 0;
        }
        return uint16((_value / _networkFeeDivisor));
    }

    /*
     * @notice With every update of the account the interest inccurred
     * @notice since the last update is calculated and added to the balance.
     * @notice The interest is calculated linearily. Effective compounding depends on frequent updates.
     * @param sender User wishing to send funds to receiver, incurring the interest(interest gets added to the balance)
     * @param receiver User receiving the funds, the beneficiary of the interest
     * @param mtime the current day since system start
     */
    function _occurredInterest(int64 _balance, uint16 _interest, uint16 _elapsed) internal pure returns (int64 interest) {
        if ((_elapsed == 0) || (_interest == 0)) {
            return;
        }
        interest = int64(_balance / (_interest * 256) * _elapsed);
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

    function uniqueIdentifier(address _A, address _B) internal pure returns (bytes32) {
        require(_A != _B);
        if (_A < _B) {
            return keccak256(_A, _B);
        } else if (_A > _B) {
            return keccak256(_B, _A);
        }
    }

    function chequeId(
        address _from,
        address _to,
        uint32 _value,
        uint16 _maxFee,
        uint16 _expiresOn,
        uint _nounce
    )
        internal
        pure
        returns (bytes32)
    {
        return keccak256(
            _from,
            _to,
            _value,
            _maxFee,
            _expiresOn,
            _nounce);
    }

    function acceptId(
        address _creditor,
        address _debtor,
        uint32 _value
    )
        internal
        pure
        returns (bytes32)
    {
        return keccak256(_creditor, _debtor, _value);
    }

    // ERC 223 Interface

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

    function _abs(int64 _balance) internal pure returns (int64 _absBalance) {
        if (_balance < 0) {
            _absBalance = - _balance;
        } else {
            _absBalance = _balance;
        }
    }

    //assemble the given address bytecode. If bytecode exists then the _addr is a contract.
    function isContract(address _addr) internal returns (bool) {
        uint length;
        assembly {
            //retrieve the size of the code on target address, this needs assembly
            length := extcodesize(_addr)
        }
        return (length > 0);
    }
}
