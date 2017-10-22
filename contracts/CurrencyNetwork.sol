pragma solidity ^0.4.11;


import "./lib/it_set_lib.sol";  // Library for Set iteration
import "./lib/ECVerify.sol";  // Library for safer ECRecovery
import "./lib/Receiver_Interface.sol";  // Library for Token Receiver ERC223 Interface
import "./lib/ERC223_Interface.sol";  // Library for Token ERC223 Interface

/*
 * CurrencyNetwork
 *
 * Main contract of Trustlines, encapsulates all creditlines and trustlines.
 * Implements ERC20 token interface and functionality, adds fees on different levels.
 *
 * Note: use of CurrentNetworkFactory is highly recommended.
 *
 * CurrencyNetworkFactory(
 *      bytes29 _tokenName,
 *      bytes3 _tokenSymbol,
 *      address _delegates,
 *      uint16 _network_fee_divisor,
 *      uint16 _capacity_fee_divisor,
 *      uint16 _imbalance_fee_divisor,
 *      uint16 _maxInterestRate)
 */
contract CurrencyNetwork is ERC223 {

    using ItSet for ItSet.AddressSet;
    mapping (bytes32 => Account) public accounts;

    // FEE GLOBAL DEFAULTS
    // Divides current value being transferred to calculate the Network fee
    uint16 network_fee_divisor;
    // Divides current value being transferred to calculate the capacity fee which equals the imbalance fee
    uint16 capacity_imbalance_fee_divisor;

    // address of governance template
    address governance;

    // meta data for token part
    string public name;
    string public symbol;
    uint8 public decimals;

    // Events
    event Approval(address indexed _owner, address indexed _spender, uint256 indexed _value);
    event Transfer(address indexed _from, address indexed _to, uint indexed _value);
    event CreditlineUpdateRequest(address indexed _creditor, address indexed _debtor, uint32 indexed _value);
    event CreditlineUpdate(address indexed _creditor, address indexed _debtor, uint32 indexed _value);
    event PathPrepared(address indexed _sender, address indexed _receiver);
    // must be deactivated due to gas costs
    event BalanceUpdate(address indexed _from, address indexed _to, int256 indexed _value);
    event ChequeCashed(address indexed _sender, address indexed _receiver, uint32 indexed _value);

    struct Path {
        // set maximum fee which is allowed for this transaction
        uint16 maxFee;
        // set complete path for transaction
        address[] path;
    }

    // for accounting balance and trustline between two users introducing fees and interests
    // currently uses 208 bits, 48 remaining
    struct Account {
        // A < B (A is the lower address)
        uint16 interestAB;          //  interest rate set by A for debt of B
        uint16 interestBA;          //  interest rate set by B for debt of A

        uint16 mtime;               //  last modification time

        uint16 feesOutstandingA;    //  fees outstanding by A
        uint16 feesOutstandingB;    //  fees outstanding by B

        uint32 creditlineAB;        //  creditline given by A to B, always positive
        uint32 creditlineBA;        //  creditline given by B to A, always positive

        int64 balanceAB;            //  balance between A and B, A->B (x(-1) for B->A)
    }

    // sha3 hash to Path for planned transfer
    mapping (bytes32 => Path) calculated_paths;
    // sha3 hash of Creditline updates, in 2PA
    mapping (bytes32 => uint16) proposedCreditlineUpdates;
    // mapping (sha3(_from, _to, _value, _expiresOn)) => depositedOn
    mapping (bytes32 => uint16) cheques;

    // TODO: this should be calculated by the relay server from events
    // friends, users address has an account with
    mapping (address => ItSet.AddressSet) friends;
    //list of all users of the system
    ItSet.AddressSet users;

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

    function CurrencyNetwork() {
        // don't do anything here due to upgradeability issues (no contructor-call on replacement).
    }

    function init(
        string _tokenName,
        string _tokenSymbol,
        uint8 _decimals,
        uint16 _network_fee_divisor,
        uint16 _capacity_imbalance_fee_divisor,
        address _governance
    ) {
        require(_decimals < 10);
        name = _tokenName;
        symbol = _tokenSymbol;
        decimals = _decimals;
        network_fee_divisor = _network_fee_divisor;
        capacity_imbalance_fee_divisor = _capacity_imbalance_fee_divisor;
        governance = _governance;
    }

    /*
     * @notice initialize contract to send `_value` token to `_to` from `msg.sender` with calculated path
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @param _maxFee Maximum for fee which occurs when the path is used for transfer
     * @param _path Path of Trustlines calculated by external service (relay server)
     */
    function prepare(address _to, uint16 _maxFee, address[] _path) external {
        calculated_paths[sha3(msg.sender, _to)] =
        Path({
        maxFee : _maxFee,
        path : _path
        });
        PathPrepared(msg.sender, _to);
    }

    /*
     * @notice initialize contract to send `_value` token to `_to` from `_from` with calculated path
     * @param _from The address of the sender
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @param _maxFee Maximum for fee which occurs when the path is used for transfer
     * @param _path Path of Trustlines calculated by external service (relay server)
     */
    function prepareFrom(address _from, address _to, uint16 _maxFee, address[] _path) external {
        calculated_paths[sha3(_from, _to)] =
        Path({
        maxFee : _maxFee,
        path : _path
        });
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
    function cashCheque(address _from, address _to, uint32 _value, uint16 _expiresOn, bytes _signature) external returns (bool success) {
        bytes32 chequeId = sha3(_from, _to, _value, _expiresOn);
        // derive address from signature
        address signer = ECVerify.ecverify(chequeId, _signature);
        // signer is address _from?
        require(signer == _from);
        // already processed?
        require(cheques[chequeId] == 0);
        // still valid?
        require(_expiresOn >= calculateMtime());
        // transfer
        transferFrom(_from, _to, _value);
        // set processed
        cheques[chequeId] = calculateMtime();
        ChequeCashed(_from, _to, _value);
        success = true;
    }

    /*
     * @notice send `_value` token to `_to` from `msg.sender`, the path must have been prepared with function `prepare` first
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     */
    function transfer(address _to, uint _value) valueWithinInt32(_value) returns (bool success) {
        uint32 value = uint32(_value);
        success = _mediatedTransferFrom(msg.sender, _to, value);
    }

    /*
     * @notice send `_value` token to `_to` from `msg.sender`, the path must have been prepared with function `prepare` first
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @param _maxFee Maximum fee the sender wants to pay
     * @param _path Path between msg.sender and _to
     */
    function transfer(address _to, uint32 _value, uint16 _maxFee, address[] _path) external returns (bool success) {
        require(_mediatedTransferFrom(msg.sender, _to, _value, _maxFee, _path));
        success = true;
    }

    /*
     * @notice `msg.sender` gives a creditline to `_debtor` of `_value` tokens, must be accepted by debtor
     * @param _debtor The account that can spend tokens up to the given amount
     * @param _value The maximum amount of tokens that can be spend
     */
    function updateCreditline(address _debtor, uint32 _value) external notSender(_debtor) {
        if (_value < getCreditline(msg.sender, _debtor)) {
            _setCreditline(msg.sender, _debtor, _value);
        } else {
            bytes32 acceptId = sha3(msg.sender, _debtor, _value);
            // currently storing the time of request to be able to remove too old ones later
            proposedCreditlineUpdates[acceptId] = calculateMtime();
            CreditlineUpdateRequest(msg.sender, _debtor, _value);
        }
    }

    /*
     * @notice `msg.sender` accepts a creditline from `_creditor` of `_value` tokens
     * @param _creditor The account that spends tokens up to the given amount
     * @param _value The maximum amount of tokens that can be spend
     * @return true, if the credit was successful
     */
    function acceptCreditline(address _creditor, uint32 _value) external returns (bool success) {
        address debtor = msg.sender;
        // retrieve acceptId to validate that updateCreditline has been called
        bytes32 acceptId = sha3(_creditor, debtor, _value);
        require(proposedCreditlineUpdates[acceptId] > 0);
        //doesnt work with testrpc, should delete the update request
        //delete proposedCreditlineUpdates[acceptId];
        _setCreditline(_creditor, debtor, _value);
    }

    function _setCreditline(address _creditor, address _debtor, uint32 _value) internal returns (bool success) {
        Account memory account = getAccount(_creditor, _debtor);
        int64 balance = account.balanceAB;

        addToUsersAndFriends(_creditor, _debtor);
        account.creditlineAB = _value;

        storeAccount(_creditor, _debtor, account);
        CreditlineUpdate(_creditor, _debtor, _value);
        success = true;
    }

    /*
     * @notice annual interest rate as byte(ir) is calculated outside and then set here.
     * @dev creditor sets the annual interestrate for outstanding amounts by debtor
     * @param _debtor Ethereum address of debtor and the byte representation(ir) of the annual interest rate
     * @param _ir new interest rate for Creditline
     */
    function __updateInterestRate(address _debtor, uint16 _ir) external returns (bool success) {
        address creditor = msg.sender;
        // TODO: check GovernanceTemplate
        Account memory account = getAccount(creditor, _debtor);
        account.interestAB = _ir;
        storeAccount(creditor, _debtor, account);
    }

    /*
     * @notice send `_value` token to `_to` from `msg.sender`
     * @param _from The address of the sender
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @return true, if the transfer was successful
     */
    function transferFrom(address _from, address _to, uint _value) valueWithinInt32(_value) public returns (bool success) {
        uint32 value = uint32(_value);
        require(_transferOnValidPath(_from, _to, value));
        success = true;
    }

    function _abs(int64 _balance) internal constant returns (int64 balance) {
        if (_balance < 0) {
            balance = - _balance;
        } else {
            balance = _balance;
        }
    }

    function _mediatedTransferFrom(address _from, address _to, uint32 _value) internal returns (bool success) {
        require(_transferOnValidPath(_from, _to, _value));
        success = true;
    }

    /*
     * @notice send `_value` token to `_to` from `msg.sender`, the path must have been prepared with function `prepare` first
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @param _maxFee the maximum fee which is accepted
     * @param _path the path of the trustlines calculated by a relay server
     */
    function _mediatedTransferFrom(address _from, address _to, uint32 _value, uint16 _maxFee, address[] _path) internal returns (bool success) {
        // check Path: is there a Path and is _to the last address? Otherwise throw
        require((_path.length > 0) && (_to == _path[_path.length - 1]));

        // calculate inverse and set as real value
        int32 rValue = int32(_value);
        uint16 fees = 0;

        for (uint i = _path.length; i > 0; i--) {
            address receiver = _path[i - 1];
            address sender;
            if (i == 1) {
                sender = _from;
            } else {
                sender = _path[i - 2];
            }
            Account memory account = getAccount(receiver, sender);
            require(account.creditlineAB > 0);
            if (i == 0) {
                fees = _calculateNetworkFee(uint32(rValue));
                account.feesOutstandingA += fees;
            }
            _transfer(sender, receiver, uint32(rValue), account);
        }
        Transfer(_from, _to, uint32(_value));
        // For ERC223, callback to receiver if it is contract
        if (isContract(_to)) {
            ContractReceiver contractReceiver = ContractReceiver(_to);
            bytes memory empty;
            contractReceiver.tokenFallback(_to, _value, empty);
        }
        success = true;
    }

    /*
     * @notice Checks for the spendable amount by spender
     * @param _spender The address from which the balance will be retrieved
     * @return spendable The spendable amount
     */
    function spendable(address _spender) public constant returns (uint spendable) {
        spendable = 0;
        var myfriends = friends[_spender].list;
        for (uint i = 0; i < myfriends.length; i++) {
            spendable += spendableTo(_spender, myfriends[i]);
        }
    }

    /*
     * @notice the maximum spendable amount by the spender to the receiver.
     * @param _spender The account spending the tokens
     * @param _receiver the receiver that receives the tokens
     * @return Amount of remaining tokens allowed to spend
     */
    function spendableTo(address _spender, address _receiver) public constant returns (uint remaining) {
        Account memory account = getAccount(_spender, _receiver);
        int64 balance = account.balanceAB;
        uint32 creditline = account.creditlineBA;
        remaining = uint(creditline + balance);
    }

    function shaOfValue(address _from, address _to, uint32 _value, uint16 _expiresOn) public constant returns (bytes32 data) {
        return sha3(_from, _to, _value, _expiresOn);
    }

    /*
     * @dev The ERC20 Token balance for the spender. This is different from the balance within a trustline.
     *      In Trustlines this is the spendable amount
     * @param _owner The address from which the balance will be retrieved
     * @return The balance
     */
    function balanceOf(address _owner) public constant returns (uint256) {
        return spendable(_owner);
    }

    /*
     * @return total amount of tokens. In Trustlines this is the sum of all creditlines
     */
    function totalSupply() public constant returns (uint256 supply) {
        supply = 0;
        var users_list = users.list;
        for (uint i = 0; i < users_list.length; i++) {
            supply += spendable(users_list[i]);
        }
    }

    /*
     * @notice Returns the trustline between A and B from the point of A
     * @param _A The account spending the tokens
     * @param _B the receiver that receives the tokens
     * @return the creditline given from A to B, the creditline given from B to A, the balance from the view of A
     */
    function trustline(address _A, address _B) public constant returns (int256[]) {
        Account memory account = getAccount(_A, _B);
        int[] memory retvals = new int[](3);
        retvals[0] = int256(account.creditlineAB);
        retvals[1] = int256(account.creditlineBA);
        retvals[2] = int256(account.balanceAB);
        return retvals;
    }

    function trustlineLen(address _A, address _B) public constant returns (uint) {
        return trustline(_A, _B).length + 2;
    }

    /*
     * @notice Gets the sum of system fees as applicable when A sends B and transfer
     * @dev Gets the sum of system fees as applicable when A sends B and transfer
     * @param Ethereum Addresses of A and B
     */
    function getFeesOutstanding(address _A, address _B) public constant returns (int fees) {
        Account memory account = getAccount(_A, _B);
        fees = account.feesOutstandingA;
    }

    // PUBLIC GETTERS

    /*
     * @param _owner The address of the account owning tokens
     * @param _spender The address of the account able to transfer the tokens
     * @return Amount tokens allowed to spent
     */
    function getCreditline(address _owner, address _spender) public constant returns (uint creditline) {
        // returns the current creditline given by A to B
        Account memory account = getAccount(_owner, _spender);
        creditline = account.creditlineAB;
    }

    /*
     * @notice returns what B owes to A
     * @dev If negative A owes B, if positive B owes A
     * @param Ethereum addresses A and B which have trustline relationship established between them
     */
    function getBalance(address _A, address _B) public constant returns (int balance) {
        Account memory account = getAccount(_A, _B);
        balance = account.balanceAB;
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

    function getUsersReturnSize() returns (uint) {
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

    function storeAccount(address _A, address _B, Account account) internal {
        Account acc = accounts[uniqueIdentifier(_A, _B)];
        if (_A < _B) {
            acc.creditlineAB = account.creditlineAB;
            acc.creditlineBA = account.creditlineBA;
            acc.interestAB = account.interestBA;
            acc.interestBA = account.interestAB;
            acc.feesOutstandingA = account.feesOutstandingA;
            acc.feesOutstandingB = account.feesOutstandingB;
            acc.mtime = account.mtime;
            acc.balanceAB = account.balanceAB;
        } else {
            acc.creditlineBA = account.creditlineAB;
            acc.creditlineAB = account.creditlineBA;
            acc.interestBA = account.interestBA;
            acc.interestAB = account.interestAB;
            acc.feesOutstandingB = account.feesOutstandingA;
            acc.feesOutstandingA = account.feesOutstandingB;
            acc.mtime = account.mtime;
            acc.balanceAB = - account.balanceAB;
        }
    }

    /*
     * @notice With every update of the account the interest inccurred
     * @notice since the last update is calculated and added to the balance.
     * @notice The interest is calculated linearily. Effective compounding depends on frequent updates.
     * @param sender User wishing to send funds to receiver, incurring the interest(interest gets added to the balance)
     * @param receiver User receiving the funds, the beneficiary of the interest
     * @param mtime the current day since system start
     */
    function occurredInterest(int64 _balance, uint16 _interest, uint16 _elapsed) public constant returns (int64 interest) {
        // Check whether request came from msg.sender otherwise anyone can call and change the mtime of the account
        if ((_elapsed == 0) || (_interest == 0)) {
            return;
        }
        interest = int64(_balance / (_interest * 256) * _elapsed);
    }

    function _transferOnValidPath(address _from, address _to, uint _value) valueWithinInt32(_value) internal returns (bool success) {
        uint32 value = uint32(_value);
        bytes32 pathId = sha3(_from, _to);
        // check Path exists and is still valid
        Path path = calculated_paths[pathId];
        if (path.path.length > 0) {
            success = _mediatedTransferFrom(_from, _to, value, path.maxFee, path.path);
        }
    }

    function _calculateNetworkFee(uint32 _value) internal returns (uint16) {
        return uint16(_value + (_value / network_fee_divisor));
    }

    function _calculateFees(uint32 _value, int64 _balance) internal returns (uint32) {
        int64 imbalance_generated = int64(_value);
        if (_balance > 0) {
            imbalance_generated = _value - _balance;
            if (imbalance_generated <= 0) {
                return 0;
            }
        }
        return uint32(uint32(imbalance_generated / capacity_imbalance_fee_divisor) + 1);  // minimum fee is 1
    }

    function _transfer(address _sender, address _receiver, uint32 _value, Account accountReceiverSender) internal {
        int64 balanceAB = accountReceiverSender.balanceAB;

        // check Creditlines (value + balance must not exceed creditline)
        uint32 creditline = accountReceiverSender.creditlineAB;
        uint32 nValue = _value - _calculateFees(_value, balanceAB);

        require(nValue + balanceAB <= creditline);

        // apply Interests
        uint16 elapsed = calculateMtime() - accountReceiverSender.mtime;
        int64 interest = occurredInterest(accountReceiverSender.balanceAB, accountReceiverSender.interestAB, elapsed);
        accountReceiverSender.balanceAB += interest;

        // store new balance
        accountReceiverSender.balanceAB = nValue + balanceAB;
        storeAccount(_receiver, _sender, accountReceiverSender);

        // Should be removed later
        BalanceUpdate(_receiver, _sender, accountReceiverSender.balanceAB);
    }

    function addToUsersAndFriends(address _A, address _B) internal {
        users.insert(_A);
        users.insert(_B);
        friends[_A].insert(_B);
        friends[_B].insert(_A);
    }

    function setAccount(address _A, address _B, uint32 clAB, uint32 clBA, uint16 iAB, uint16 iBA, uint16 fA, uint16 fB, uint16 mtime, int64 balance) external {
        Account memory account;
        account.creditlineAB = clAB;
        account.creditlineBA = clBA;
        account.interestAB = iAB;
        account.interestBA = iBA;
        account.feesOutstandingA = fA;
        account.feesOutstandingB = fB;
        account.mtime = mtime;
        account.balanceAB = balance;
        storeAccount(_A, _B, account);
    }

    function getAccountExt(address _A, address _B) public constant returns (int, int, int, int, int, int, int, int) {
        Account account = accounts[uniqueIdentifier(_A, _B)];
        if (_A < _B) {
            // View of the Account if the address A < B
            return (account.creditlineAB,
                    account.creditlineBA,
                    account.interestAB,
                    account.interestBA,
                    account.feesOutstandingA,
                    account.feesOutstandingB,
                    account.mtime,
                    account.balanceAB);
        } else {
            // View of the account if Address A > B
            return (account.creditlineBA,
                    account.creditlineAB,
                    account.interestBA,
                    account.interestAB,
                    account.feesOutstandingB,
                    account.feesOutstandingA,
                    account.mtime,
                    -account.balanceAB);
        }
    }

    function getAccountExtLen() constant returns (uint) {
        return 8 * 32 + 2;
    }

    function getAccount(address _A, address _B) internal constant returns (Account acc) {
        Account account = accounts[uniqueIdentifier(_A, _B)];
        if (_A < _B) {
            acc.creditlineAB = account.creditlineAB;
            acc.creditlineBA = account.creditlineBA;
            acc.interestAB = account.interestBA;
            acc.interestBA = account.interestAB;
            acc.feesOutstandingA = account.feesOutstandingA;
            acc.feesOutstandingB = account.feesOutstandingB;
            acc.mtime = account.mtime;
            acc.balanceAB = account.balanceAB;
        } else {
            acc.creditlineBA = account.creditlineAB;
            acc.creditlineAB = account.creditlineBA;
            acc.interestBA = account.interestBA;
            acc.interestAB = account.interestAB;
            acc.feesOutstandingB = account.feesOutstandingA;
            acc.feesOutstandingA = account.feesOutstandingB;
            acc.mtime = account.mtime;
            acc.balanceAB = -account.balanceAB;
        }
    }

    function uniqueIdentifier(address _A, address _B) internal constant returns (bytes32) {
        require(_A != _B);
        if (_A < _B) {
            return sha3(_A, _B);
        } else if (_A > _B) {
            return sha3(_B, _A);
        }
    }

    // ERC 223 Interface

    function name() constant returns (string) {
        return name;
    }

    function nameLen() constant returns (uint) {
        return bytes(name).length;
    }

    function symbol() constant returns (string) {
        return symbol;
    }

    function symbolLen() constant returns (uint) {
        return bytes(symbol).length;
    }

    function decimals() constant returns (uint8) {
        return decimals;
    }

    function transfer(address _to, uint _value, bytes _data) returns (bool ok) {
        return transfer(_to, _value);
    }

    //assemble the given address bytecode. If bytecode exists then the _addr is a contract.
    function isContract(address _addr) private returns (bool) {
        uint length;
        assembly {
            //retrieve the size of the code on target address, this needs assembly
            length := extcodesize(_addr)
        }
        return (length > 0);
    }
}
