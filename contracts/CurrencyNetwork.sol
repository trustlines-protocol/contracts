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
    uint16 constant network_fee_divisor = 1000;
    // Divides current value being transferred to calculate the capacity fee
    uint16 constant capacity_fee_divisor = 500;
    // Divides imbalance that current value transfer introduces to calculate the imbalance fee
    uint16 constant imbalance_fee_divisor = 250;
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
    event CreditlineUpdateRequest(address _creditor, address _debtor, uint256 _value);
    event CreditlineUpdate(address _creditor, address _debtor, uint256 _value);
    // currently deactivated due to gas costs
    // event BalanceUpdate(address _from, address _to, int256 _value);

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

    // friends, useers address has an account with
    mapping (address => ItSet.AddressSet) friends;
    //list of all users of the system
    ItSet.AddressSet users;
    
    modifier notSender(address _sender) {
        assert(_sender != msg.sender);
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
    function prepare(address _to, uint32 _value, uint16 _maxFee, address[] _path) {
        calculated_paths[sha3(msg.sender, _to, _value)] = 
            Path(
                {expiresOn : uint16(calculateMtime().add16(1)),
                 maxFee : _maxFee,
                 path : _path
                }
            );
    }
    
   /*
     * @notice initialize contract to send `_value` token to `_to` from `_from` with calculated path
     * @param _from The address of the sender
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @param _maxFee Maximum for fee which occurs when the path is used for transfer
     * @param _path Path of Trustlines calculated by external service (relay server)
     */
     function prepareFrom(address _from, address _to, uint32 _value, uint16 _maxFee, address[] _path) {
        calculated_paths[sha3(_from, _to, _value)] = 
            Path(
                {expiresOn : uint16(calculateMtime().add16(1)),
                 maxFee : _maxFee,
                 path : _path
                }
            );
    }
    
    /*
     * @notice `msg.sender` approves `_spender` to spend `_value` tokens, is currently not supported for Trustlines
     * @param _spender The address of the account able to transfer the tokens
     * @param _value The amount of wei to be approved for transfer
     */
    function approve(address _spender, uint _value) {
        // currently not supported, since there is no logical equivalent
        throw;
    }

    /*
     * @notice For Trustlines allowance equals the creditline
     * @return Creditline between _owner and _spender
     */
    function allowance(address _owner, address _spender) constant returns (uint) {
        return getCreditline(_owner, _spender);
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
    function cashCheque(address _from, address _to, uint32 _value, uint16 _expiresOn, bytes _signature) returns (bool success) {
        bytes32 chequeId = sha3(_from, _to, _value, _expiresOn);
        // derive address from signature
        address signer = ECVerify.ecverify(chequeId, _signature);
        // signer is address _from?
        assert(signer == _from);
        // already processed?
        assert(cheques[chequeId] == 0);
        // still valid?
        assert(_expiresOn >= calculateMtime());
        // transfer
        transferFrom(_from, _to, _value);
        // set processed
        cheques[chequeId] = calculateMtime();
        success = true;
    }

    /*
     * @notice send `_value` token to `_to` from `msg.sender`
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @return Whether the transfer was successful or not
     */
    function transfer(address _to, uint _value) valueWithinInt32(_value) {
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
    function transferFrom(address _from, address _to, uint _value) valueWithinInt32(_value) {
        uint32 value = uint32(_value);
        if (getCreditline(_from, msg.sender) > 0) {
            bytes32 pathId = sha3(_from, _to, _value);
            _transferOnValidPath(pathId, _to, value);
        }
    }

    function _transferOnValidPath(bytes32 _pathId, address _to, uint _value) internal {
        require(_value < 2**32);
        uint32 value = uint32(_value);
        // check Path exists and is still valid
        Path path = calculated_paths[_pathId];
        if (path.expiresOn > 0) {
            // is path still valid?
            if (calculateMtime() > path.expiresOn) {
                throw;
            } else {
                mediatedTransfer(_to, value);
            }
        }
    }

    /*
     * @notice send `_value` token to `_to` from `msg.sender`, the path must have been prepared with function `prepare` first
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     */
    function mediatedTransfer(address _to, uint32 _value) returns (bool success) {
        bytes32 pathId = sha3(msg.sender, _to, _value);
        address[] _path = calculated_paths[pathId].path;
        if (_path.length == 0 || _to != _path[_path.length - 1]) {
            throw;
        }

        uint16 fees = 0;
        address sender = msg.sender;
        for (uint i = 0;i < _path.length; i++) {
            _to = _path[i];
            int64 balance = store().getBalance(sender, _to);
            if (i == 0) {
                fees = Fees.applyNetworkFee(sender, _to, _value, network_fee_divisor);
                store().updateOutstandingFees(sender, _to, fees);
            } else {
                fees = Fees.deductedTransferFees(balance, sender, _to, _value, capacity_fee_divisor, imbalance_fee_divisor);
                _value = _value.sub32(fees);
            }
            _transfer(sender, _to, _value);
            sender = _to;
        }
        Transfer(msg.sender, _to, _value);
    }

    function _balance(int64 _balanceAB) internal returns (int64 balance){
        if (_balanceAB > 0) { // netted balance, value B owes to A(if positive)
            balance = _balanceAB; // interest rate set by A for debt of B
        } else {
            balance = -_balanceAB; // interest rate set by B for debt of A
        }
    }

    function _interest(int64 _balanceAB, uint16 _interestAB, uint16 _interestBA) internal returns (uint16 interest){
        if (_balanceAB > 0) { // netted balance, value B owes to A(if positive)
            interest = _interestAB; // interest rate set by A for debt of B
        } else {
            interest = _interestBA; // interest rate set by B for debt of A
        }
    }

    function _transfer(address _sender, address _receiver, uint32 _value) internal  {
        // why??? should be _sender, _receiver
        int64 balance = store().getBalance(_receiver, _sender);

        // check Creditlines (value + balance must not exceed creditline)
        uint32 creditline = store().getCreditline(_receiver, _sender);
        assert(_value + balance <= creditline);

        // apply Interests
        uint16 timediff = calculateMtime() - store().getLastModification(_sender, _receiver);
        uint16 interestAB = store().getInterest(_sender, _receiver);
        uint16 interestBA = store().getInterest(_receiver, _sender);
        int64 interest = Interests.occurredInterest(_balance(balance), _interest(balance, interestAB, interestBA), timediff);
        store().addToBalance(_sender, _receiver, interest);

        // store new balance
        store().storeBalance(_receiver, _sender, _value + balance);
    }

    /*
     * @notice `msg.sender` gives a creditline to `_debtor` of `_value` tokens, must be accepted by debtor
     * @param _debtor The account that can spend tokens up to the given amount
     * @param _value The maximum amount of tokens that can be spend
     */
    function updateCreditline(address _debtor, uint32 _value) notSender(_debtor) {
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
    function acceptCreditline(address _creditor, uint32 _value) returns (bool success) {
        address _debtor = msg.sender;
        // retrieve acceptId to validate that updateCreditline has been called
        bytes32 acceptId = sha3(_creditor, _debtor, _value);
        assert(proposedCreditlineUpdates[acceptId] > 0);
        //doesnt work with testrpc
        //delete proposedCreditlineUpdates[acceptId];

        int64 balance = store().getBalance(_creditor, _debtor);
        // do not allow creditline below balance
        assert(_value >= balance);

        if (!users.contains(_creditor)) {
            users.insert(_creditor);
        }
        if (!users.contains(_debtor)) {
            users.insert(_debtor);
        }
        if (!friends[_creditor].contains(_debtor)) {
            friends[_creditor].insert(_debtor);
        }
        if (!friends[_debtor].contains(_creditor)) {
            friends[_debtor].insert(_creditor);
        }

        store().storeCreditline(_creditor, _debtor, _value);
        CreditlineUpdate(_creditor, _debtor, _value);
        success = true;
    }

    /*
     * @notice Checks for the spendable amount by spender
     * @param _spender The address from which the balance will be retrieved
     * @return spendable The spendable amount
     */
    function spendable(address _spender) constant returns (uint spendable) {
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
    function spendableTo(address _spender, address _receiver) constant returns (uint remaining) {
        var balance = store().getBalance(_spender, _receiver);
        var creditline = store().getCreditline(_receiver, _spender);
        remaining = uint(creditline + balance);
    }

    function store() internal returns (EternalStorage es) {
        es = EternalStorage(eternalStorage);
    }

    /*
     * @dev The ERC20 Token balance for the spender. This is different from the balance within a trustline.
     *      In Trustlines this is the spendable amount
     * @param _owner The address from which the balance will be retrieved
     * @return The balance
     */
    function balanceOf(address _owner) constant returns (uint256) {
        return spendable(_owner);
    }

    /*
     * @return total amount of tokens. In Trustlines this is the sum of all creditlines
     */
    function totalSupply() constant returns (uint256 supply) {
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
    function trustline(address _A, address _B) constant returns (int creditlineAB, int creditlineBA, int balanceAB) {
        creditlineAB = store().getCreditline(_A, _B);
        creditlineBA = store().getCreditline(_B, _A);
        balanceAB = store().getBalance(_A, _B);
    }

    /*
     * @notice annual interest rate as byte(ir) is calculated outside and then set here.
     * @dev creditor sets the annual interestrate for outstanding amounts by debtor
     * @param _debtor Ethereum address of debtor and the byte representation(ir) of the annual interest rate
     * @param _ir new interest rate for Creditline
     */
    function updateInterestRate(address _debtor, uint16 _ir) returns (bool success) {
        address creditor = msg.sender;
        store().updateInterest(creditor, _debtor, _ir);
    }

    /*
     * @notice Gets the sum of system fees as applicable when A sends B and transfer
     * @dev Gets the sum of system fees as applicable when A sends B and transfer
     * @param Ethereum Addresses of A and B
     */
    function getFeesOutstanding(address _A, address _B) constant returns (int fees) {
        fees = store().getOutstandingFees(_A, _B);
    }

    // PUBLIC GETTERS

    /*
     * @param _owner The address of the account owning tokens
     * @param _spender The address of the account able to transfer the tokens
     * @return Amount tokens allowed to spent
     */
    function getCreditline(address _owner, address _spender) constant returns (uint creditline) {
        // returns the current creditline given by A to B
        creditline = store().getCreditline(_owner, _spender);
    }

    /*
     * @notice returns what B owes to A
     * @dev If negative A owes B, if positive B owes A
     * @param Ethereum addresses A and B which have trustline relationship established between them
     */
    function getBalance(address _A, address _B) constant returns (int balance) {
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
    function calculateMtime() public returns (uint16 mtime){
        mtime = uint16((now/(24*60*60)) - ((2017 - 1970)* 365));
    }

}
