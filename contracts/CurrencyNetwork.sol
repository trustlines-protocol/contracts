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
contract CurrencyNetwork {

    using ItSet for ItSet.AddressSet;


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
    bytes29 public name;
    bytes3 public symbol;
    uint8 public decimals = 6;

    EternalStorage eternalStorage;

    // Events
    event Approval(address _owner, address _spender, uint256 _value);
    event Transfer(address _from, address _to, uint _value);
    event CreditlineUpdateRequest(address _creditor, address _debtor, uint32 _value);
    event CreditlineUpdate(address _creditor, address _debtor, uint32 _value);
    event PathPrepared(address _sender, address _receiver);
    // must be deactivated due to gas costs
    event BalanceUpdate(address _from, address _to, int256 _value);
    event Debug(uint32 v1, int v2, int v3, int v4);

    struct Path {
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
    mapping (bytes32 => uint16) cheques;
    // allowance to msg.sender to send uint32 to address
    mapping (address => mapping (address => uint32)) allowed;

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
        bytes29 _tokenName,
        bytes3 _tokenSymbol,
        address _eternalStorage
    ) {
        name = _tokenName;       // Set the name for display purposes
        symbol = _tokenSymbol;   // Set the symbol for display purposes
        eternalStorage = EternalStorage(_eternalStorage);
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
        success = true;
    }

    /*
     * @notice send `_value` token to `_to` from `msg.sender`, the path must have been prepared with function `prepare` first
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     */
    function transfer(address _to, uint32 _value) external returns (bool success) {
        success = _mediatedTransferFrom(msg.sender, _to, _value);
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
        //TODO reduce must be possible without accept
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

    function _setCreditline(address _creditor, address _debtor, uint32 _value) internal returns (bool success){
        Trustline.Account memory account = getAccountInt(_creditor, _debtor);
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
        Trustline.Account memory account = getAccountInt(creditor, _debtor);
        account.interestAB = _ir;
        storeAccount(creditor, _debtor, account);
    }

    /*
     * @notice `msg.sender` approves `_spender` to spend `_value` tokens, is currently not supported for Trustlines
     * @param _spender The address of the account able to transfer the tokens
     * @param _value The amount of wei to be approved for transfer
     */
    function approve(address _spender,  uint _value) valueWithinInt32(_value) public returns (bool success){
        uint32 value = uint32(_value);
        address creditor = msg.sender;

        allowed[creditor][_spender] = value;
        Approval(creditor, _spender, value);
        success = true;
    }

    /*
     * @notice send `_value` token to `_to` from `msg.sender`
     * @param _from The address of the sender
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @return true, if the transfer was successful
     */
    function transferFrom(address _from, address _to, uint _value) valueWithinInt32(_value) public returns (bool success){
        uint32 value = uint32(_value);
        if (allowed[_from][msg.sender] >= value) {
            allowed[_from][msg.sender] -= value;
            require(_transferOnValidPath(_from, _to, value));
            success = true;
        } else {
            success = false;
        }
    }

    function _abs(int64 _balance) internal constant returns (int64 balance)  {
        if (_balance < 0) {
            balance = -_balance;
        } else {
            balance = _balance;
        }
    }

    function _calculateNetworkFee(uint32 _value) internal returns (uint16) {
        return uint16(_value / network_fee_divisor);
    }

    function _calculateCapacityFee(uint32 _value) internal returns (uint16) {
        return uint16(_value / capacity_fee_divisor);
    }

    function _calculateImbalanceFee(uint32 _value, int64 _balance) internal returns (int32) {
        return int32((_abs(_balance - _value) - _abs(_balance)) / imbalance_fee_divisor);
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
        require ((_path.length > 0) && (_to == _path[_path.length - 1]));

        // calculate inverse and set as real value
        int32 rValue = int32(_value);
        uint16 fees = 0;

        for (uint i = _path.length; i>0; i--) {
            address receiver = _path[i-1];
            address sender;
            if (i == 1) {
                sender = _from;
            } else {
                sender = _path[i-2];
            }
            Trustline.Account memory account = getAccountInt(receiver, sender);
            if (i == 0) {
                fees = _calculateNetworkFee(uint32(rValue));
                account.feesOutstandingA += fees;
            }
            _transfer(sender, receiver, uint32(rValue), account);
            // TODO: remove due to gas costs
            BalanceUpdate(sender, _to, uint32(rValue));
        }
        Transfer(_from, _to, uint32(_value));
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
        Trustline.Account memory account = getAccountInt(_spender, _receiver);

        int64 balance = account.balanceAB;
        uint32 creditline = account.creditlineBA;
        remaining = uint(creditline + balance);
    }

    /*
     * @notice For Trustlines allowance equals the creditline
     * @return Creditline between _owner and _spender
     */
    function allowance(address _owner, address _spender) public constant returns (uint32) {
        return allowed[_owner][_spender];
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
        Trustline.Account memory account = getAccountInt(_A, _B);
        creditlineAB = account.creditlineAB;
        creditlineBA = account.creditlineBA;
        balanceAB = account.balanceAB;
    }

    /*
     * @notice Gets the sum of system fees as applicable when A sends B and transfer
     * @dev Gets the sum of system fees as applicable when A sends B and transfer
     * @param Ethereum Addresses of A and B
     */
    function getFeesOutstanding(address _A, address _B) public constant returns (int fees) {
        Trustline.Account memory account = getAccountInt(_A, _B);
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
        Trustline.Account memory account = getAccountInt(_owner, _spender);
        creditline = account.creditlineAB;
    }

    /*
     * @notice returns what B owes to A
     * @dev If negative A owes B, if positive B owes A, delegates to EternalStorage
     * @param Ethereum addresses A and B which have trustline relationship established between them
     */
    function getBalance(address _A, address _B) public constant returns (int balance) {
        Trustline.Account memory account = getAccountInt(_A, _B);
        balance = account.balanceAB;
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
    function getAccountExt(address _A, address _B) public constant returns (int, int, int, int, int, int, int, int) {
        return eternalStorage.getAccount(_A, _B);
    }

    function getAccountInt(address _A, address _B) internal constant returns (Trustline.Account account) {
        var (clAB, clBA, iAB, iBA, fA, fB, mtime, balance) = eternalStorage.getAccount(_A, _B);
        account =  Trustline.Account({
            creditlineAB : uint32(clAB),
            creditlineBA : uint32(clBA),
            interestAB : uint16(iAB),
            interestBA : uint16(iBA),
            feesOutstandingA : uint16(fA),
            feesOutstandingB : uint16(fB),
            mtime : uint16(mtime),
            balanceAB : int48(balance)
        });
    }

    function storeAccount(address _A, address _B, Trustline.Account account) internal {
        eternalStorage.setAccount(
            _A,
            _B,
            account.creditlineAB,
            account.creditlineBA,
            account.interestAB,
            account.interestBA,
            account.feesOutstandingA,
            account.feesOutstandingB,
            account.mtime,
            account.balanceAB
        );
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

    function _transferOnValidPath(address _from, address _to, uint _value) valueWithinInt32(_value) internal returns (bool success){
        uint32 value = uint32(_value);
        bytes32 pathId = sha3(_from, _to);
        // check Path exists and is still valid
        Path path = calculated_paths[pathId];
        if (path.path.length > 0) {
            success = _mediatedTransferFrom(_from, _to, value, path.maxFee, path.path);
        }
    }

    function _calculateNetworkFeeInv(uint32 _value) internal returns (uint16) {
        return uint16(_value + (_value/network_fee_divisor));
    }

    function _calculateCapacityFeeInv(uint32 _value) internal returns (uint16) {
        return uint16(_value + (_value/capacity_fee_divisor));
    }

    function _calculateImbalanceFeeInv(uint32 _value, int64 _balance) internal returns (int64) {
        int64 absBalance = _abs(_balance);
        int64 imbalanceDiff = (_balance - _value) - absBalance;
        int64 imbalanceFee = imbalanceDiff / imbalance_fee_divisor;
        return _value + imbalanceFee;
    }

    function _transfer(address _sender, address _receiver, uint32 _value, Trustline.Account account) internal  {
        int64 balanceAB = account.balanceAB;

        // check Creditlines (value + balance must not exceed creditline)
        //TODO: check side of account or rename account to accountReceiverSender
        uint32 creditline = account.creditlineAB;
        uint32 nValue = uint32(_calculateCapacityFeeInv(_value));
        nValue = uint32(_calculateImbalanceFeeInv(nValue, balanceAB));

        require(nValue + balanceAB <= creditline);

        // apply Interests
        uint16 elapsed = calculateMtime() - account.mtime;
        int64 interest = occurredInterest(account.balanceAB, account.interestAB, elapsed);
        account.balanceAB += interest;

        // store new balance
        account.balanceAB = nValue + balanceAB;
        // DEBUG
        Debug(nValue, _value, 0, account.balanceAB);
        storeAccount(_receiver, _sender, account);
    }

    function addToUsersAndFriends(address _A, address _B) internal {
        users.insert(_A);
        users.insert(_B);
        friends[_A].insert(_B);
        friends[_B].insert(_A);
    }

}
