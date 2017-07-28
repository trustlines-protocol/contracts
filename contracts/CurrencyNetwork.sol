pragma solidity ^0.4.0;

import "./lib/it_set_lib.sol";      // Library for Set iteration
import "./lib/ERC20.sol";           // modified version of "zeppelin": "1.0.5": token/ERC20
import "./lib/SafeMath.sol";        // modified version of "zeppelin": "1.0.5": SafeMath
import "./lib/ECVerify.sol";        // Library for safer ECRecovery
import "./Trustline.sol";           // data structure and functionality for a Trustline
import "./Interests.sol";           // interest calculator for path in CurrencyNetwork
import "./Fees.sol";                // fees calculator for path in CurrencyNetwork
import "./EternalStorage.sol";      // eternal storage for upgrade purposes
import "./ICurrencyNetwork.sol";    // interface description for CurrencyNetwork

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
contract CurrencyNetwork is ICurrencyNetwork, ERC20 {

    using ItSet for ItSet.AddressSet;
    using SafeMath for int64;
    using SafeMath for int256;
    using SafeMath for uint16;
    using SafeMath for uint24;
    using SafeMath for uint32;

    // FEE GLOBAL DEFAULTS
    
    // Divides current value being transferred to calculate the Network fee
    uint16 constant network_fee_divisor = 10;
    // Divides current value being transferred to calculate the capacity fee
    uint16 constant capacity_fee_divisor = 20;
    // Divides imbalance that current value transfer introduces to calculate the imbalance fee
    uint16 constant imbalance_fee_divisor = 25;
    // Base decimal units in which we carry out operations in this token.
    uint32 constant base_unit_multiplier = 100000;

    // meta data for token part
    bytes32 public name;
    bytes3 public symbol;
    uint8 public decimals = 5;

    address eternalStorage;

    // Events
    event Approval(address _owner, address _spender, uint256 _value);
    event Transfer(address _from, address _to, uint _value);
    event CreditlineUpdateRequest(address _creditor, address _debtor, uint32 _value);
    event CreditlineUpdate(address _creditor, address _debtor, uint32 _value);
    event PathPrepared(address _sender, address _receiver, uint32 _value);
    // must be deactivated due to gas costs
    event BalanceUpdate(address _from, address _to, int256 _value);

    struct Path {
        // set expiration date for Path
        uint16 expiresOn;
        // set maximum fee which is allowed for this transaction
        uint16 maxFee;
        // set complete path for transaction 
        address[] path;
    }

    // sha3 hash to Path for planned transfer
    mapping (bytes32 => Path) calculated_paths;
    // sha3 hash of Creditline updates, in 2PA
    mapping (bytes32 => uint16) proposedCreditlineUpdates;
    // mapping (sha3(_from, _to, _value, _expiresOn)) => depositedOn
    mapping(bytes32 => uint16) cheques;

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
        require(_value < 2**32);
        _;
    }

    function CurrencyNetwork(
        bytes32 _tokenName,
        bytes3 _tokenSymbol,
        address _eternalStorage
    ) {
        name = _tokenName;       // Set the name for display purposes
        symbol = _tokenSymbol;   // Set the symbol for display purposes
        eternalStorage = _eternalStorage;
    }

    /*
     * @notice initialize contract to send `_value` token to `_to` from `msg.sender` with calculated path
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @param _maxFee Maximum for fee which occurs when the path is used for transfer
     * @param _path Path of Trustlines calculated by external service (relay server)
     */
    function prepare(address _to, uint32 _value, uint16 _maxFee, address[] _path) external {
        calculated_paths[sha3(msg.sender, _to, _value)] = 
            Path(
                {expiresOn : uint16(calculateMtime().add16(1)),
                 maxFee : _maxFee,
                 path : _path
                }
            );
        PathPrepared(msg.sender, _to, _value);
    }
    
   /*
     * @notice initialize contract to send `_value` token to `_to` from `_from` with calculated path
     * @param _from The address of the sender
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @param _maxFee Maximum for fee which occurs when the path is used for transfer
     * @param _path Path of Trustlines calculated by external service (relay server)
     */
     function prepareFrom(address _from, address _to, uint32 _value, uint16 _maxFee, address[] _path) external {
        calculated_paths[sha3(_from, _to, _value)] = 
            Path(
                {expiresOn : uint16(calculateMtime().add16(1)),
                 maxFee : _maxFee,
                 path : _path
                }
            );
    }

    function echo() constant returns (uint) {
        return 1;
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
        success = true;
    }

    /*
     * @notice send `_value` token to `_to` from `msg.sender`, the path must have been prepared with function `prepare` first
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     */
    function mediatedTransfer(address _to, uint32 _value) external returns (bool success) {
        success = mediatedTransfer(msg.sender, _to, _value);
    }

    /*
     * @notice send `_value` token to `_to` from `msg.sender`, the path must have been prepared with function `prepare` first
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @dev note: a pat has to be prepared before this method can be used
     */

    function mediatedTransfer(address _from, address _to, uint32 _value) internal returns (bool success) {
        bytes32 pathId = sha3(_from, _to, _value);
        address[] _path = calculated_paths[pathId].path;
        success = mediatedTransfer(_from, _to, _value, calculated_paths[pathId].maxFee, _path);
    }

    /*
     * @notice send `_value` token to `_to` from `msg.sender`, the path must have been prepared with function `prepare` first
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @param _maxFee the maximum fee which is accepted
     * @param _path the path of the trustlines calculated by a relay server
     */
    function mediatedTransfer(address _to, uint32 _value, uint16 _maxFee, address[] _path) external returns (bool success) {
        success = mediatedTransfer(msg.sender, _to, _value, _maxFee, _path);
    }

    /*
     * @notice `msg.sender` gives a creditline to `_debtor` of `_value` tokens, must be accepted by debtor
     * @param _debtor The account that can spend tokens up to the given amount
     * @param _value The maximum amount of tokens that can be spend
     */
    function updateCreditline(address _debtor, uint32 _value) external notSender(_debtor) {
        bytes32 acceptId = sha3(msg.sender, _debtor, _value);
        proposedCreditlineUpdates[acceptId] = calculateMtime();
        CreditlineUpdateRequest(msg.sender, _debtor, _value);
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
        //doesnt work with testrpc
        //delete proposedCreditlineUpdates[acceptId];

        int64 balance = store().getBalance(_creditor, debtor);
        // do not allow creditline below balance
        require(_value >= balance);

        addToUsersAndFriends(_creditor, debtor);

        store().storeCreditline(_creditor, debtor, _value);
        CreditlineUpdate(_creditor, debtor, _value);
        success = true;
    }

    /*
     * @notice annual interest rate as byte(ir) is calculated outside and then set here.
     * @dev creditor sets the annual interestrate for outstanding amounts by debtor
     * @param _debtor Ethereum address of debtor and the byte representation(ir) of the annual interest rate
     * @param _ir new interest rate for Creditline
     */
    function updateInterestRate(address _debtor, uint16 _ir) external returns (bool success) {
        address creditor = msg.sender;
        store().updateInterest(creditor, _debtor, _ir);
    }

    /*
     * @notice `msg.sender` approves `_spender` to spend `_value` tokens, is currently not supported for Trustlines
     * @param _spender The address of the account able to transfer the tokens
     * @param _value The amount of wei to be approved for transfer
     */
    function approve(address _spender,  uint _value) valueWithinInt32(_value) public {
        uint32 value = uint32(_value);
        address creditor = msg.sender;

        int64 balance = store().getBalance(creditor, _spender);
        // do not allow creditline below balance
        require(value >= balance);

        addToUsersAndFriends(creditor, _spender);

        store().storeCreditline(creditor, _spender, value);
        Approval(creditor, _spender, value);
    }

    /*
     * @notice send `_value` token to `_to` from `msg.sender`
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @return Whether the transfer was successful or not
     */
    function transfer(address _to, uint _value) valueWithinInt32(_value) public {
        uint32 value = uint32(_value);

        // get unique Trustline between msg.sender and _to
        _transfer(msg.sender, _to, value);
        Transfer(msg.sender, _to, value);
    }

    /*
     * @notice send `_value` token to `_to` from `msg.sender`
     * @param _from The address of the sender
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @return true, if the transfer was successful
     */
    function transferFrom(address _from, address _to, uint _value) valueWithinInt32(_value) public {
        uint32 value = uint32(_value);
        if (getCreditline(_from, _to) > 0) {
            require(_transferOnValidPath(_from, _to, value));
        }
    }

    function calculateFees(address _from, address _to, uint32 _value, uint16 _maxFee, address[] _path) public constant returns (int64) {
        // check Path: is there a Path and is _to the last address? Otherwise throw
        require ((_path.length > 0) && (_to == _path[_path.length - 1]));

        int64 valueBefore = _value;
        int64 valueAfter = _value;
        address sender = _from;
        uint pathLength = _path.length;
        for (uint i = pathLength; i > 0; i--) {
            address receiver = _path[i-1];
            if (i == 1) {
                valueAfter = (valueBefore / (1-(1/network_fee_divisor)));
            }
            valueAfter += (valueBefore / (1-(1/capacity_fee_divisor))) - valueBefore;
            int64 balance = store().getBalance(sender, receiver);
            int64 absBalance = abs(balance);
            if ((abs(balance - valueAfter) - absBalance) > 0) {
                valueAfter += ((1/imbalance_fee_divisor) * absBalance + balance * (1/imbalance_fee_divisor) - valueBefore) / ((1/imbalance_fee_divisor)-1);
            } else {
                valueAfter += (-(1/imbalance_fee_divisor) * absBalance + balance * (1/imbalance_fee_divisor) + valueBefore) / ((1/imbalance_fee_divisor)+1);
            }
            sender = receiver;
            valueBefore = valueAfter;
        }
        return valueAfter;
    }

    function abs(int64 _balance) internal constant returns (int64 balance)  {
        if (_balance < 0) {
            balance = -_balance;
        } else {
            balance = _balance;
        }
    }

    function applyNetworkFee(address _sender, address _receiver, uint32 _value) internal returns (uint16) {

    }

    function applyCapacityFee(address _sender, address _receiver, uint32 _value) internal returns (uint16) {

    }

    function applyImbalanceFee(address _sender, address _receiver, uint32 _value) internal returns (uint16) {

    }

    /*
     * @notice send `_value` token to `_to` from `msg.sender`, the path must have been prepared with function `prepare` first
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @param _maxFee the maximum fee which is accepted
     * @param _path the path of the trustlines calculated by a relay server
     */
    function mediatedTransfer(address _from, address _to, uint32 _value, uint16 _maxFee, address[] _path) internal returns (bool success) {
        // check Path: is there a Path and is _to the last address? Otherwise throw
        require ((_path.length > 0) && (_to == _path[_path.length - 1]));

        uint16 fees = 0;
        address sender = _from;
        for (uint i = 0;i < _path.length; i++) {
            _to = _path[i];
            int64 balance = store().getBalance(sender, _to);
            if (i == 0) {
                fees = applyNetworkFee(sender, _to, _value);
            }
            fees += applyCapacityFee(sender, _to, _value);
            fees += applyImbalanceFee(sender, _to, _value);
            store().updateOutstandingFees(sender, _to, fees);
            _transfer(sender, _to, _value);
            sender = _to;
            // TODO: remove due to gas costs
            BalanceUpdate(sender, _to, _value);
        }
        Transfer(_from, _to, _value);
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
        for(uint i = 0; i < myfriends.length; i++) {
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
        int64 balance = store().getBalance(_spender, _receiver);
        uint32 creditline = store().getCreditline(_receiver, _spender);
        remaining = uint(creditline + balance);
    }

    /*
     * @notice For Trustlines allowance equals the creditline
     * @return Creditline between _owner and _spender
     */
    function allowance(address _owner, address _spender) public constant returns (uint) {
        return getCreditline(_owner, _spender);
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
        for(uint i = 0; i < users_list.length; i++) {
            supply += spendable(users_list[i]);
        }
    }

    /*
     * @notice Returns the trustline between A and B from the point of A
     * @param _A The account spending the tokens
     * @param _B the receiver that receives the tokens
     * @return the creditline given from A to B, the creditline given from B to A, the balance from the view of A
     */
    function trustline(address _A, address _B) public constant returns (int creditlineAB, int creditlineBA, int balanceAB) {
        creditlineAB = store().getCreditline(_A, _B);
        creditlineBA = store().getCreditline(_B, _A);
        balanceAB = store().getBalance(_A, _B);
    }

    /*
     * @notice Gets the sum of system fees as applicable when A sends B and transfer
     * @dev Gets the sum of system fees as applicable when A sends B and transfer
     * @param Ethereum Addresses of A and B
     */
    function getFeesOutstanding(address _A, address _B) public constant returns (int fees) {
        fees = store().getOutstandingFees(_A, _B);
    }

    // PUBLIC GETTERS

    /*
     * @param _owner The address of the account owning tokens
     * @param _spender The address of the account able to transfer the tokens
     * @return Amount tokens allowed to spent
     */
    function getCreditline(address _owner, address _spender) public constant returns (uint creditline) {
        // returns the current creditline given by A to B
        creditline = store().getCreditline(_owner, _spender);
    }

    /*
     * @notice returns what B owes to A
     * @dev If negative A owes B, if positive B owes A, delegates to EternalStorage
     * @param Ethereum addresses A and B which have trustline relationship established between them
     */
    function getBalance(address _A, address _B) public constant returns (int balance) {
        balance = store().getBalance(_A, _B);
    }

    /*
     * @notice gets friends of user
     * @param Ethereum Address of the user
     */
    function getFriends(address _user) public constant returns (address[]) {
        return friends[_user].list;
    }

    /*
     * @notice gets friends of user
     * @param Ethereum Address of the user
     */

    function getUsers() public constant returns (address[]) {
        return users.list;
    }

    /*
     * @notice Calculates the current modification day since system start.
     * @notice now is an alias for block.timestamp gives the epoch time of the current block.
     */
    function calculateMtime() public constant returns (uint16 mtime){
        mtime = uint16((now/(24*60*60)) - ((2017 - 1970)* 365));
    }

    // delegates to EternalStorage
    function getAccount(address _A, address _B) public constant returns (int, int, int, int, int, int, int, int) {
        return store().getAccount(_A, _B);
    }

    // delegates to EternalStorage
    function getInterestRate(address _A, address _B) public constant returns (uint16) {
        return store().getInterestRate(_A, _B);
    }

    // delegates to EternalStorage and Fees library
    function imbalanceFee(address _A, address _B, uint32 _value) public constant returns (uint16 fees) {
        int64 balance = store().getBalance(_A, _B);
        fees = Fees.imbalanceFee(balance, _A, _B, _value, imbalance_fee_divisor);
    }

    // delegates to Fees library
    function capacityFee(uint32 _value) public constant returns (uint16 fees) {
        fees = Fees.capacityFee(_value, capacity_fee_divisor);
    }

    // delegates to EternalStorage and Fees library
    function deductedTransferFees(address _sender, address _receiver, uint32 _value) public constant returns (uint16 fees) {
        int64 balance = store().getBalance(_sender, _receiver);
        fees = Fees.deductedTransferFees(balance, _sender, _receiver, _value, capacity_fee_divisor, imbalance_fee_divisor);
    }

    /*
     * @notice returns the linear interest on the imbalance since last account update.
     * @notice negative if A is indebted to B, positive otherwise
     * @dev delegates to EternalStorage and Interests library
     */
    function occurredInterest(address _sender, address _receiver, uint16 _mtime) public constant returns (int) {
        uint16 elapsed = _mtime - store().getLastModification(_sender, _receiver);
        int64 balance = store().getBalance(_sender, _receiver);
        if (balance < 0) {
            balance = -balance;
        }
        uint16 interest = store().getInterestRate(_sender, _receiver);
        return Interests.occurredInterest(balance, interest, elapsed);
    }

    function _transferOnValidPath(address _from, address _to, uint _value) valueWithinInt32(_value) internal returns (bool success){
        uint32 value = uint32(_value);
        bytes32 pathId = sha3(_from, _to, value);
        // check Path exists and is still valid
        Path path = calculated_paths[pathId];
        if (path.expiresOn > 0) {
            // is path still valid?
            require(calculateMtime() <= path.expiresOn);
            success = mediatedTransfer(_from, _to, value);
        }
    }

    function _transfer(address _sender, address _receiver, uint32 _value) internal  {
        // why??? should be _sender, _receiver
        int64 balanceAB = store().getBalance(_receiver, _sender);

        // check Creditlines (value + balance must not exceed creditline)
        uint32 creditline = store().getCreditline(_receiver, _sender);
        require(_value + balanceAB <= creditline);

        // apply Interests
        uint16 timediff = calculateMtime() - store().getLastModification(_receiver, _sender);
        int64 balance;
        uint16 interestRate;
        (balance, interestRate) = _getBalanceAndInterestRate(_sender, _receiver, balanceAB);
        int64 occurredInterest = Interests.occurredInterest(balance, interestRate, timediff);
        store().addToBalance(_receiver, _sender, occurredInterest);

        // apply Fees
        uint16 fees = Fees.applyNetworkFee(_sender, _receiver, _value, network_fee_divisor);
        store().updateOutstandingFees(_sender, _receiver, fees);

        // store new balance
        store().storeBalance(_receiver, _sender, _value + balanceAB);
    }

    function store() internal returns (EternalStorage es) {
        es = EternalStorage(eternalStorage);
    }

    function addToUsersAndFriends(address _A, address _B) internal {
        if (!users.contains(_A)) {
            users.insert(_A);
        }
        if (!users.contains(_B)) {
            users.insert(_B);
        }
        if (!friends[_A].contains(_B)) {
            friends[_A].insert(_B);
        }
        if (!friends[_A].contains(_A)) {
            friends[_B].insert(_A);
        }
    }

    function _getBalanceAndInterestRate(address _sender, address _receiver, int64 _balanceAB) internal constant returns (int64 balance, uint16 interestRate) {
        if (_balanceAB > 0) { // netted balance, value B owes to A(if positive)
            balance = _balanceAB; // interest rate set by A for debt of B
            interestRate = store().getInterestRate(_receiver, _sender);
        } else {
            balance = -_balanceAB; // interest rate set by B for debt of A
            interestRate = store().getInterestRate(_sender, _receiver);
        }
    }
}
