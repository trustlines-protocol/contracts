pragma solidity ^0.4.0;

import "./lib/it_set_lib.sol";  // Library for Set iteration
import "./lib/ERC20.sol";       // modified version of "zeppelin": "1.0.5": token/ERC20
import "./lib/SafeMath.sol";    // modified version of "zeppelin": "1.0.5": SafeMath
import "./lib/ECVerify.sol";    // Library for safer ECRecovery
import "./Trustline.sol";       // data structure and functionality for a Trustline
import "./Interests.sol";       // interest calculator for path in CurrencyNetwork
import "./Fees.sol";            // fees calculator for path in CurrencyNetwork

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
contract CurrencyNetwork is ERC20 {

    using ItSet for ItSet.AddressSet;
    using SafeMath for int48;
    using SafeMath for int256;
    using SafeMath for uint16;
    using SafeMath for uint24;
    using SafeMath for uint32;

    using Trustline for Trustline.Account;
    using Interests for Trustline.Account;
    using Fees for Trustline.Account;

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
    uint8 public decimals = 5;

    // Events
    event Approval(address _owner, address _spender, uint256 _value);
    // currently deactivated due to gas costs
    // event Balance(address indexed _from, address indexed _to, int256 _value);
    event Transfer(address _from, address _to, uint _value);
    event CreditlineUpdateRequest(address _creditor, address _debtor, uint256 _value);
    event CreditlineUpdate(address _creditor, address _debtor, uint256 _value);
    event BalanceUpdate(address _from, address _to, int256 _value);

    struct Path {
        // set expiration date for Path
        uint16 expiresOn;
        // set maximum fee which is allowed for this transaction
        uint16 maxFee;
        // set complete path for transaction 
        address[] path;
    }

    // sha3 hash to account, see key-functions and Account
    mapping (bytes32 => Trustline.Account) accounts;
    // friends, useers address has an account with
    mapping (address => ItSet.AddressSet) friends;
    // sha3 hash to Path for planned transfer
    mapping (bytes32 => Path) calculated_paths;
    // sha3 hash of Creditline updates, in 2PA
    mapping (bytes32 => uint16) proposedCreditlineUpdates;
    // mapping (sha3(_from, _to, _value, _expiresOn)) => depositedOn
    mapping(bytes32 => uint16) cheques;

    //list of all users of the system
    ItSet.AddressSet users;
    
    modifier notSender(address _sender) {
        assert(_sender != msg.sender);
        _;
    }

    function CurrencyNetwork(
        bytes29 tokenName,
        bytes3 tokenSymbol
    ) {
        name = tokenName;  // Set the name for display purposes
        symbol = tokenSymbol;  // Set the symbol for display purposes
    }

    /*
     * @notice initialize contract to send `_value` token to `_to` from `msg.sender` with calculated path
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @return Whether the init was successful or not
     */
    function prepare(address _to, uint24 _value, uint16 _maxFee, address[] _path) {
        calculated_paths[sha3(msg.sender, _to, _value)] = 
            Path({expiresOn : uint16(calculateMtime().add16(1)), maxFee : _maxFee, path : _path});
    }
    
    /*
     * @notice initialize contract to send `_value` token to `_to` from `_from` with calculated path
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @return Whether the init was successful or not
     */
    function prepareFrom(address _from, address _to, uint24 _value, uint16 _maxFee, address[] _path) {
        calculated_paths[sha3(_from, _to, _value)] = 
            Path({expiresOn : uint16(calculateMtime().add16(1)), maxFee : _maxFee, path : _path});
    }
    
    /*
     * @notice `msg.sender` approves `_spender` to spend `_value` tokens
     * @param _spender The address of the account able to transfer the tokens
     * @param _value The amount of wei to be approved for transfer
     * @return Whether the approval was successful or not
     */
    function approve(address _spender, uint _value) {
        throw;
    }

    /*
     * @notice For Trustlines allowance equals the creditline
     */
    function allowance(address _owner, address _spender) constant returns (uint) {
        return getCreditline(_owner, _spender);
    }

    /*
     * @notice cashCheque required a signature which must be provided by the UI
     */
    function cashCheque(address _from, address _to, uint _value, uint16 _expiresOn, bytes _signature) returns (bool success) {
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
    function transfer(address _to, uint256 _value)  {
        require(_value < 2**24);
        uint24 value = uint24(_value);
        Trustline.Account account = accounts[keyBalance(msg.sender, _to)];
        if (!_transfer(account, msg.sender, _to, value, calculateMtime())) {
            throw;
        }
        Transfer(msg.sender, _to, value);
    }

    /*
     * @notice send `_value` token to `_to` from `msg.sender`
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @return Whether the transfer was successful or not
     */
    function transferFrom(address _from, address _to, uint _value) {
        require(value < 2**24);
        uint24 value = uint24(_value);
        if (getCreditline(_from, msg.sender) > 0) {
            bytes32 pathId = sha3(_from, _to, _value);
            _transferOnValidPath(pathId, _to, value);
        }
    }

    function _transferOnValidPath(bytes32 _pathId, address _to, uint _value) internal {
        require(_value < 2**24);
        Path path = calculated_paths[_pathId];
        uint24 value = uint24(_value);
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
     * @notice send `_value` token to `_to` from `msg.sender`
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @param _path The path over which the token is sent
     */
    function mediatedTransfer(address _to, uint24 _value) returns (bool success) {
        require(_value < 2**24);
        address sender = msg.sender;
        uint24 value = uint24(_value);
        uint16 fees = 0;
        uint16 mtime = uint16(calculateMtime()); // The day from system start on which transaction performed
        bytes32 pathId = sha3(msg.sender, _to, _value);
        address[] _path = calculated_paths[pathId].path;
        if (_path.length == 0 || _to != _path[_path.length - 1]) {
            throw;
        }
        for (uint i = 0;i < _path.length; i++) {
            _to = _path[i];
            Trustline.Account account = accounts[keyBalance(sender, _to)];
            if (i == 0) {
                account.applyNetworkFee(sender, _to, value, network_fee_divisor);
            } else {
                fees = account.deductedTransferFees(sender, _to, uint24(value), uint16(capacity_fee_divisor), uint16(imbalance_fee_divisor));
                value = value.sub24(uint24(fees));
            }
            success = _transfer(account, sender, _to, value, mtime);
            // have to throw here to adhere to specification (ERC20 interface)
            if (!success)
                throw;
            sender = _to;
        }
        Transfer(msg.sender, _to, _value);
    }

    function _transfer(Trustline.Account storage _account, address _sender, address _receiver, uint24 _value, uint16 _mtime) internal returns (bool success) {
        // necessary? if(value <= 0) return false;
        _account.applyInterest(_mtime);
        if (_sender < _receiver) {
            // cast to int48 might be wrong, check range firs
            if (_value.sub(_account.balanceAB) > int48(_account.creditlineBA)) {
                return false;
            }

            _account.balanceAB = _account.balanceAB.sub48(_value);
        } else {
            if (_value.add(_account.balanceAB) > int48(_account.creditlineAB)) {
                return false;
            }

            _account.balanceAB = _account.balanceAB.add48(_value);
        }
        return true;
    }

    /*
     * @notice `msg.sender` gives a creditline to `_debtor` of `_value` tokens, must be accepted by debtor
     * @param _debtor The account that can spend tokens up to the given amount
     * @param _value The maximum amount of tokens that can be spend
     */
    function updateCreditline(address _debtor, uint32 _value) notSender(_debtor) {
        require(_value < 2**32);
        uint32 value = uint32(_value);
        
        bytes32 acceptId = sha3(msg.sender, _debtor, value);
        proposedCreditlineUpdates[acceptId] = calculateMtime();
    }

    /*
     * @notice `msg.sender` accepts a creditline from `_creditor` of `_value` tokens
     * @param _creditor The account that spends tokens up to the given amount
     * @param _value The maximum amount of tokens that can be spend
     * @return Whether the credit was successful or not
     */
    function acceptCreditline(address _creditor, uint32 _value) returns (bool success) {
        require(_value < 2**32);
        uint32 value = uint32(_value);
        address _debtor = msg.sender;

        bytes32 acceptId = sha3(_creditor, _debtor, value);
        assert(proposedCreditlineUpdates[acceptId] > 0);
        //doesnt work with testrpc
        //delete proposedCreditlineUpdates[acceptId];

        Trustline.Account account = accounts[keyBalance(_creditor, _debtor)];
        var balance = account.loadBalance(_creditor, _debtor);

        // onboard users and debtors
        // what if they already exist? => approve(...)
        users.insert(_creditor);
        users.insert(_debtor);
        friends[_creditor].insert(_debtor);
        friends[_debtor].insert(_creditor);

        assert(value >= 0);
        require(value >= balance);
        account.storeCreditline(_creditor, _debtor, value);
        CreditlineUpdate(_creditor, _debtor, value);
        success = true;    
    }

    /*
     * @dev Checks for the spendable amount by spender
     * @param _spender The address from which the balance will be retrieved
     * @return spendable The spendable amount
     */
    function spendable(address _spender) constant returns (uint256 spendable) {
        spendable = 0;
        var myfriends = friends[_spender].list;
        for(uint i = 0; i < myfriends.length; i++) {
            spendable += spendableTo(_spender, myfriends[i]);
        }
    }

    /*
     * @dev the maximum spendable amount by the spender to the receiver.
     * @param _spender The account spending the tokens
     * @param _receiver the receiver that receives the tokens
     * @return Amount of remaining tokens allowed to spend
     */    
    function spendableTo(address _spender, address _receiver) constant returns (uint256 remaining) {
        // returns the current trustline given by A to B
        Trustline.Account account = accounts[keyBalance(_spender, _receiver)];

        var balance = uint(account.loadBalance(_spender, _receiver));
        var creditline = uint(account.loadCreditline(_receiver, _spender));
        remaining = creditline + balance;
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

    /// @return total amount of tokens. In Trustlines this is the sum of all creditlines
    function totalSupply() constant returns (uint256 supply) {
        supply = 0;
        var users_list = users.list;
        for(uint i = 0; i < users_list.length; i++) {
            supply += spendable(users_list[i]);
        }
    }

    /*
     * @dev Returns the trustline between A and B from the point of A
     * @param _A The account spending the tokens
     * @param _B the receiver that receives the tokens
     * @return the creditline given from A to B, the creditline given from B to A, the balance from the point of A
     */
    function trustline(address _A, address _B) constant returns (int creditlineAB, int creditlineBA, int balanceAB) {
        Trustline.Account account = accounts[keyBalance(_A, _B)];
        creditlineAB = account.loadCreditline(_A, _B);
        creditlineBA = account.loadCreditline(_B, _A);
        balanceAB = account.loadBalance(_A, _B);
    }

    /*
     * @notice annual interest rate as byte(ir) is calculated outside and then set here.
     * @dev creditor sets the annual interestrate for outstanding amounts by debtor
     * @param Ethereum address of debtor and the byte representation(ir) of the annual interest rate
     */
    function updateInterestRate(address _debtor, uint16 _ir) returns (bool success) {
        address creditor = msg.sender;
        Trustline.Account account = accounts[keyBalance(creditor, _debtor)];
        if (creditor < _debtor) {
            account.interestAB = _ir;
        } else {
            account.interestBA = _ir;
        }
        success = true;
    }

    /*
     * @notice Gets the sum of system fees as applicable when A sends B and transfer
     * @dev Gets the sum of system fees as applicable when A sends B and transfer
     * @param Ethereum Addresses of A and B
     */
    function getFeesOutstanding(address _A, address _B) constant returns (int fees) {
        Trustline.Account account = accounts[keyBalance(_A, _B)];
        if (_A < _B) {
            return account.feesOutstandingA;
        } else {
            return account.feesOutstandingB;
        }
    }

    // PUBLIC GETTERS
    
    /*
     * @param _owner The address of the account owning tokens
     * @param _spender The address of the account able to transfer the tokens
     * @return Amount tokens allowed to spent
     */
    function getCreditline(address _owner, address _spender) constant returns (uint256 creditline) {
        // returns the current creditline given by A to B
        Trustline.Account account = accounts[keyBalance(_owner, _spender)];
        if (_owner < _spender) {
            creditline = uint(account.creditlineAB);
        }
        else {
            creditline = uint(account.creditlineBA);
        }
    }

    /*
     * @notice returns what B owes to A
     * @dev If negative A owes B, if positive B owes A
     * @param Ethereum addresses A and B which have trustline relationship established between them
     */
    function getBalance(address _A, address _B) constant returns (int balance) {
        Trustline.Account account = accounts[keyBalance(_A, _B)];
        if (_A < _B) {
            balance = account.balanceAB;
        }
        else {
            // negated so that same view is provided if A > B
            balance = -account.balanceAB;
        }
    }

    /*
     * @notice Gives a view of the current state of the account struct for the particular pair of A and B
     * @dev Gives a view of the current state of the account struct for the particular pair of A and B
     * @param Ethereum Addresses of A and B
     */
    function getAccount(address _A, address _B) constant returns (int, int, int, int, int, int, int, int) {
        Trustline.Account account = accounts[keyBalance(_A, _B)];
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
         }
         else{
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

    // ACCESS FOR TRUSTLINE-ACCOUNTS

    /*
     * @notice Calculates the current modification day since system start.
     * @notice now is an alias for block.timestamp gives the epoch time of the current block.
     */
    function calculateMtime() public returns (uint16 mtime){
        mtime = uint16((now/(24*60*60)) - ((2017 - 1970)* 365));
    }

    /*
     * @notice hash to look up the account between A and B in accounts
     * @dev hash to look up the account between A and B in accounts
     * @param Two Ethereum addresses in the account pair
     */
    function keyBalance(address _A, address _B) internal constant returns (bytes32) {
        if (_A < _B) {
            return sha3(_A, _B);
        }
        else if (_A > _B) {
            return sha3(_B, _A);
        }
        else {
            // A == B not allowed
            throw;
        }
    }

}
