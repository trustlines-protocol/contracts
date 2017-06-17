pragma solidity ^0.4.11;
import "./it_set_lib.sol";

// Implements a subset of the ERC 20 Token standard: https://github.com/ethereum/EIPs/issues/20
contract ERC20Token {
    function transfer(address _to, uint256 _value) returns (bool success);

    function totalSupply() constant returns (uint256 supply);
    function balanceOf(address _owner) constant returns (uint256 balance);

    event Transfer(address indexed _from, address indexed _to, uint256 _value);
}


// Use network of debt relationships to support multihop payments
contract Trustlines is ERC20Token {

    // Iterable Set
    using ItSet for ItSet.AddressSet;

    // meta data
    string public name;
    string public symbol;
    uint8 public decimals;

    // Events
    event CreditlineUpdate(address indexed _creditor, address indexed _debtor, uint256 _value);
    event BalanceUpdate(address indexed _from, address indexed _to, int256 _value);
    event Transfer(address indexed _from, address indexed _to, uint256 _value);

    // mapping of sha3 hash of two users to account, see hashFunc and Account
    mapping (bytes32 => int256) internal balances;
    mapping (bytes32 => int256) internal creditlines;
    // mapping for the users a user has a trustline with
    mapping (address => ItSet.AddressSet) internal _friends;

    // set of all users of the system
    ItSet.AddressSet internal _users;


    function Trustlines (string tokenName, string tokenSymbol, uint8 decimalUnits) {
        name = tokenName;  // Set the name for display purposes
        symbol = tokenSymbol;  // Set the symbol for display purposes
        decimals = decimalUnits;  // Amount of decimals for display purposes
    }

    // check value is inbounds for accounting to prevent overflows
    modifier valueWithinInt192(uint256 value)
    {
        require(value < 2**192);
        _;
    }

    // public functions

    /// @notice send `_value` tokens to `_to` from `msg.sender`
    /// @dev sender and recipient must have a trustline with enough credit
    /// @param _to The address of the recipient
    /// @param _value The amount of tokens to be transferred, needs to fit in int192
    /// @return Whether the transfer was successful or not
    function transfer(address _to, uint256 _value) valueWithinInt192(_value) returns (bool success) {
        int256 value = int256(_value);
        _transfer(msg.sender, _to, value);
        Transfer(msg.sender, _to, _value);
        success = true;
    }

    /// @notice send `_value` token to `_to` from `msg.sender`
    /// @dev send tokens over the given path.
    /// @param _to The address of the recipient
    /// @param _value The amount of token to be transferred
    /// @param _path The path over which the token is sent. The path must include the recipient and exclude the sender
    ///              The path must have enough capacity for the transfer
    /// @return Whether the transfer was successful or not
    function mediatedTransfer(address _to, uint256 _value, address[] _path) valueWithinInt192(_value) returns (bool success) {
        // for all addresses in path[:-1] the accumulated balance over all their accounts won't change
        address sender = msg.sender;
        int256 value = int256(_value);
        uint8 idx = 0;
        require(_path.length != 0);
        require(_to == _path[_path.length - 1]);

        while(idx < _path.length){
            _to = _path[idx];
            _transfer(sender, _to, value);
            sender = _to;
            idx++;
        }
        Transfer(msg.sender, _to, _value);
        success = true;
    }

    /// @notice `msg.sender` sets a creditline for `_debtor` of `_value` tokens
    /// @param _debtor The account that can spend tokens up to the given amount
    /// @param _value The maximum amount of tokens that can be spend
    /// @return Whether the credit was successful or not
    function updateCreditline(address _debtor, uint256 _value) valueWithinInt192(_value) returns (bool success) {
        int256 value = int256(_value);
        address _creditor = msg.sender;

        var balance = loadBalance(_creditor, _debtor);

        // onboard users and debtors
        _users.insert(_creditor);
        _users.insert(_debtor);
        _friends[_creditor].insert(_debtor);
        _friends[_debtor].insert(_creditor);

        assert(value >= 0);
        require(value >= balance);
        storeCreditline(_creditor, _debtor, value);
        CreditlineUpdate(_creditor, _debtor, _value);
        success = true;
    }

    /// @dev Checks for the spendable amount by spender
    /// @param _spender The address from which the balance will be retrieved
    /// @return spendable The spendable amount
    function spendable(address _spender) constant returns (uint256 spendable) {
        spendable = 0;
        var myfriends = _friends[_spender].list;
        for(uint i = 0; i < myfriends.length; i++) {
            spendable += spendableTo(_spender, myfriends[i]);
        }
    }

    /// @dev the maximum spendable amount by the spender to the receiver.
    /// @param _spender The account spending the tokens
    /// @param _receiver the receiver that receives the tokens
    /// @return Amount of remaining tokens allowed to spend
    function spendableTo(address _spender, address _receiver) constant returns (uint256 remaining) {
        // returns the current trustline given by A to B
        var balance = uint(loadBalance(_spender, _receiver));
        var creditline = uint(loadCreditline(_receiver, _spender));
        remaining = creditline + balance;
    }

    /// @dev The ERC20 Token balance for the spender. This is different from the balance within a trustline.
    ///      In Trustlines this is the spendable amount
    /// @param _owner The address from which the balance will be retrieved
    /// @return The balance
    function balanceOf(address _owner) constant returns (uint256) {
        return spendable(_owner);
    }

    /// @return total amount of tokens. In Trustlines this is the sum of all creditlines
    function totalSupply() constant returns (uint256 supply) {
        supply = 0;
        var users = _users.list;
        for(uint i = 0; i < users.length; i++) {
            supply += spendable(users[i]);
        }
    }

    /// @dev Returns the trustline between A and B from the point of A
    /// @param _A The account spending the tokens
    /// @param _B the receiver that receives the tokens
    /// @return the creditline given from A to B, the creditline given from B to A, the balance from the point of A
    function trustline(address _A, address _B) constant returns (int creditlineAB, int creditlineBA, int balanceAB) {
        creditlineAB = loadCreditline(_A, _B);
        creditlineBA = loadCreditline(_B, _A);
        balanceAB = loadBalance(_A, _B);
    }

    function friends(address _user) public constant returns (address[]) {
        return _friends[_user].list;
    }

    function users() public constant returns (address[]) {
        return _users.list;
    }

    // internal and private functions

    // key to look up the the balance There is only one balance between two users
    function keyBalance(address _A, address _B) internal constant returns (bytes32) {
        if (_A < _B) {
            return sha3(_A, _B);
        } else if (_A > _B) {
            return sha3(_B, _A);
        } else {
            // A == B not allowed
            throw;
        }
    }

    // load balance from storage
    function loadBalance(address _A, address _B) internal constant returns (int256) {
        int256 balance;
        balance = balances[keyBalance(_A, _B)];
        if (_A > _B) {
            balance = -balance;
        }
        return balance;
    }

    // store balance to storage
    function storeBalance(address _A, address _B, int256 balance) internal {
        if (_A < _B) {
             balances[keyBalance(_A, _B)] = balance;
        } else {
             balances[keyBalance(_A, _B)] = -balance;
        }
    }

    // key to look up the the creditline given from _A to _B
    function keyCreditline(address _A, address _B) internal constant returns (bytes32) {
        if (_A == _B) {
            throw;
        }
        return sha3(_A, _B);
    }

    // load the Creditline given from _A to _B from storage
    function loadCreditline(address _A, address _B) internal constant returns (int256) {
        int256 creditline = creditlines[keyCreditline(_A, _B)];
        return creditline;
    }

    // store the Creditline given from _A to _B
    function storeCreditline(address _A, address _B, int256 creditline) internal {
        creditlines[keyCreditline(_A, _B)] = creditline;
    }

    // internal transfer function
    // sender transfers value to receiver
    // receiver will only accept if the total value owed by sender is within the creditline given to sender
    function _transfer(address _sender, address _receiver, int256 _value) private returns (bool success) {
        assert(_value >= 0);

        var balance = loadBalance(_receiver, _sender);
        var creditline = loadCreditline(_receiver, _sender);
        // check if updated balance is within creditline
        require(_value + balance <= creditline);

        int256 newBalance = balance + _value;
        storeBalance(_receiver, _sender, newBalance);
        BalanceUpdate(_receiver, _sender, newBalance);
        success = true;
    }
}
