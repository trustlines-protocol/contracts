pragma solidity ^0.4.2;
import "./it_set_lib.sol";

contract TLTokenBusiness {
    using ItSet for ItSet.AddressSet;

    //fee globals
    // Divides current value being transferred to calculate the Network fee
    uint16 constant network_fee_divisor = 1000;
    // Divides current value being transferred to calculate the capacity fee
    uint16 constant capacity_fee_divisor = 500;
    // Divides imbalance that current value transfer introduces to calculate the imbalance fee
    uint16 constant imbalance_fee_divisor = 250;
    // Base decimal units in which we carry out operations in this token.
    uint32 constant base_unit_multiplier = 100000;
    // meta data
    bytes29 public name;
    bytes3 public symbol;
    uint8 public decimals = 5;

    // Events
    event Approval(address indexed _owner, address indexed _spender, uint256 _value);
    event Balance(address indexed _from, address indexed _to, int256 _value);
    event Transfer(address indexed _from, address indexed _to, uint256 _value);

    // for accounting balance and trustline between two users introducing fees and interests
    struct Account {
        // A < B (A is the lower address)
        uint16 interestAB;      //  interest rate set by A for debt of B
        uint16 interestBA;      //  interest rate set by B for debt of A

        uint16 mtime;           //  last modification time

        uint16 feesOutstandingA;           //  fees outstanding by A
        uint16 feesOutstandingB;           //  fees outstanding by B

        uint32 creditlineAB;    //  creditline given by A to B, always positive
        uint32 creditlineBA;    //  creditline given by B to A, always positive

        int48 balanceAB;        //  netted balance, value B owes to A (if positive)
    }

    // sha3 hash to account, see hashFunc and Account
    mapping (bytes32 => Account) accounts;
    // friends, useers address has an account with
    mapping (address => ItSet.AddressSet) friends;

    //list of all users of the system
    ItSet.AddressSet users;

    function TLTokenBusiness(
        bytes29 tokenName,
        bytes3 tokenSymbol
    ) {
        name = tokenName;  // Set the name for display purposes
        symbol = tokenSymbol;  // Set the symbol for display purposes
    }

    /*
     * @notice hash to look up the account between A and B in accounts
     * @param Two Ethereum addresses in the account pair
     */
    function hashFunc(address A, address B) constant returns (bytes32) {
        // account where A == B is not allowed
        if (A == B) {
            throw;
        }
        else if (A < B) {
            return sha3(A, B);
        }
        else {
            return sha3(B, A);
        }
    }

    /*
     * @notice Gets the users whom creditor has given a creditline
     * @param Ethereum Address of the creditor
     */
    function getFriends(address creditor) constant returns (address[]) {
        return friends[creditor].list;
    }
    /*
     * @notice Gets users using the this token
     * @dev Gets users using the this token
     * @param
     */
    function getUsers() constant returns (address[]) {
        return users.list;
    }

    /*
     * @notice `msg.sender` approves `_spender` to spend `_value` tokens
     * @param _spender The address of the account able to transfer the tokens
     * @param _value The amount of wei to be approved for transfer
     * @return Whether the approval was successful or not
     */
    function approve (address _spender,  uint32 _value) returns (bool success) {
        if (_value < 0) return false;

        address creditor = msg.sender;
        users.insert(creditor);
        users.insert(_spender);
        friends[creditor].insert(_spender);
        friends[_spender].insert(creditor);
        Account account = accounts[hashFunc(creditor, _spender)];
        if (creditor < _spender) {
            // can not set creditline under balance
            if (_value < account.balanceAB) {
                return false;
            }
            account.creditlineAB = _value;
        }
        else {
            // can not set creditline under balance
            if (_value < -account.balanceAB) {
                return false;
            }
            account.creditlineBA = _value ;
        }
        Approval(creditor, _spender, uint(_value));
        success = true;
    }

    /*
     * @notice annual interest rate as byte(ir) is calculated outside and then set here.
     * @dev creditor sets the annual interestrate for outstanding amounts by debtor
     * @param Ethereum address of debtor and the byte representation(ir) of the annual interest rate
     */
    function updateInterestRate(address debtor, uint16 ir) returns (bool success) {
        address creditor = msg.sender;
        Account account = accounts[hashFunc(creditor, debtor)];
        if (creditor < debtor) {
            account.interestAB = ir;
        } else {
            account.interestBA = ir;
        }
        success = true;
    }

    /*
     * @param _owner The address of the account owning tokens
     * @param _spender The address of the account able to transfer the tokens
     * @return Amount tokens allowed to spent
     */
    function getCreditline(address _owner, address _spender) constant returns (uint256 creditline) {
        // returns the current creditline given by A to B
        Account account = accounts[hashFunc(_owner, _spender)];
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
    function getBalance(address A, address B) constant returns (int balance) {
        Account account = accounts[hashFunc(A, B)];
        if (A < B) {
            balance = account.balanceAB;
        }
        else {
            // negated because it provides a view of the balance from the B side
            balance = -account.balanceAB;
        }
    }

    /*
     * @notice This function returns the annual interest rate as byte
     * @dev need to converted to know the actual value of annual interest rate
     * @param Ethereum addresses of A and B
     * @return Interest rate set by A for the debt of B
     */
    function getInterestRate(address A, address B) constant returns (uint256 interestrate) {
        Account account = accounts[hashFunc(A, B)];
        if (A < B) {
            return account.interestAB;
        }
        else {
            return account.interestBA;
          }
    }

    /*
     * @notice Gets the sum of system fees as applicable when A sends B and transfer
     * @dev Gets the sum of system fees as applicable when A sends B and transfer
     * @param Ethereum Addresses of A and B
     */
    function getFeesOutstanding(address A, address B) constant returns (int fees) {
        Account account = accounts[hashFunc(A, B)];
        if (A < B) {
            return account.feesOutstandingA;
        } else {
            return account.feesOutstandingB;
        }
    }

    /*
     * @notice Gives a view of the current state of the account struct for the particular pair of A and B
     * @dev Gives a view of the current state of the account struct for the particular pair of A and B
     * @param Ethereum Addresses of A and B
     */
    function getAccount(address A, address B) constant returns (int, int, int, int, int, int, int, int) {
        Account account = accounts[hashFunc(A, B)];
        if (A < B) {
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
         else {
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
     * @notice send `_value` token to `_to` from `msg.sender`
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @return Whether the transfer was successful or not
     */
    function transfer(address _to, uint32 _value) returns (bool success) {
        address sender = msg.sender;
        //applyNetworkFee(sender, _to, _value);
        uint16 mtime = uint16(calculateMtime()); // The day from system start on which transaction performed
        success = _transfer(sender, _to, _value, mtime, 0);
        if (success) {
            Transfer(msg.sender, _to, uint(_value));
        } else {
            throw;// throwing because if transfer is unsuccessfull the networkfee and interest should not be applied.
        }
        return success;
    }

    /*
     * @notice Please remember in this function the value should already be converted to the base multiplier unit
     * @notice (i.e multiplied by base_unit_multiplier) outside the contract before calling this function.
     * @param
     */
    function _transfer(address sender, address receiver, uint32 value, uint16 mtime, uint iteration) internal returns (bool success) {
        if (value <= 0)
            return false;
        Account account = accounts[hashFunc(sender, receiver)];
        int48 balanceAB = account.balanceAB;
        int addedImbalance = 0;
        int newBalance = 0;
        //applyInterest(sender, receiver, mtime);
        //code to calculate Interest
        if (mtime > account.mtime) {
            int elapsed = mtime - account.mtime;
            uint16 interestByte = 0;
            if (account.balanceAB > 0) { // netted balance, value B owes to A(if positive)
                interestByte = account.interestAB; // interest rate set by A for debt of B
            } else {
                interestByte = account.interestBA; // interest rate set by B for debt of A
            }
            int interest = calculateInterest(interestByte, account.balanceAB) * elapsed;
            account.mtime = mtime;
            account.balanceAB += int48(interest);
        }
        // end of interest calc
        if (sender < receiver) {
            if (value - account.balanceAB > account.creditlineBA * base_unit_multiplier) {
                return false;
            }
            if (iteration == 0) {
                account.feesOutstandingA += uint16(calculateNetworkFee(int(value)));
            } else {
                if (balanceAB <= 0) {
                    addedImbalance = value;
                } else {
                // positive hence receiver indebted to sender so if the newBalance is smaller then zero we introduce imbalance
                    newBalance = balanceAB - value;
                    if(newBalance < 0) addedImbalance = -newBalance;
                }
                value -= uint32(capacityFee(value) + calculateImbalanceFee(addedImbalance));
            }
            account.balanceAB -= value ;
            //Balance(sender,receiver, account.balanceAB); // This event may be used for debugging purposes only
        } else {
            if (value + account.balanceAB > account.creditlineAB * base_unit_multiplier) {
                return false;
            }
            if (iteration == 0) {
                account.feesOutstandingB += uint16(calculateNetworkFee(int(value)));
            } else {
                //sender address is greater, here semantics will be opposite of the one above
                // positive hence sender is indebted to receiver so addedImbalance is the incoming value
                if (balanceAB >= 0) {
                    addedImbalance = value;
                } else {
                    // negative hence receiver is indebted to the sender so if the newBalance is greater than zero we introduce imbalance
                    newBalance = balanceAB + value;
                    if(newBalance > 0) addedImbalance = newBalance;
                }
                value -= uint32(capacityFee(value) + calculateImbalanceFee(addedImbalance));
            }
            account.balanceAB += value;
            //Balance(receiver, sender, account.balanceAB); // This event may be used for debugging purposes only
        }
        return true;
    }

    /*
     * @notice send `_value` token to `_to` from `msg.sender`
     * @param _to The address of the recipient
     * @param _value The amount of token to be transferred
     * @param _path The path over which the token is sent
     */
    function mediatedTransfer(address _to, uint32 _value, address[] _path) returns (bool success) {
        address sender = msg.sender;
        uint32 value = _value;
        int fees = 0;
        uint16 mtime = uint16(calculateMtime()); // The day from system start on which transaction performed
        if (_path.length == 0 || _to != _path[_path.length - 1]) {
            return false;
        }
        for (uint i = 0;i < _path.length; i++) {
            _to = _path[i];
            /*
            if(i == 0){
                //applyNetworkFee(sender, _to, _value);
            }

            if(i > 0){
                fees = deductedTransferFees(sender, _to, _value);
                value -= uint32(fees);
            }
            */
            success = _transfer(sender, _to, value, mtime, i);
            if(!success)
                throw;
            sender = _to;
        }
        Transfer(msg.sender, _to, uint(_value));
        return true;
    }

    /*
     * @notice With every update of the account the interest inccurred
     * @notice since the last update is calculated and added to the balance.
     * @notice The interest is calculated linearily. Effective compounding depends on frequent updates.
     * @param sender User wishing to send funds to receiver, incurring the interest(interest gets added to the balance)
     * @param receiver User receiving the funds, the beneficiary of the interest
     * @param mtime the current day since system start
     */
    function applyInterest(address sender, address receiver, uint16 mtime) internal {
        // Check whether request came from msg.sender otherwise anyone can call and change the mtime of the account
        Account account = accounts[hashFunc(sender, receiver)];
        if (mtime == account.mtime)
            return;
        //int interestFromByte = occurredInterest(sender, receiver, mtime);
        int elapsed = mtime - account.mtime;
        uint16 interestByte = 0;
        if (account.balanceAB > 0) { // netted balance, value B owes to A(if positive)
            interestByte = account.interestAB; // interest rate set by A for debt of B
        } else {
            interestByte = account.interestBA; // interest rate set by B for debt of A
        }
        int interest = calculateInterest(interestByte, account.balanceAB) * elapsed;
        account.mtime = mtime;
        account.balanceAB += int48(interest);
    }

    /*
     * @notice The network fee is payable by the inititator of a transfer.
     * @notice It is tracked in the outgoing account to avoid updating a user global storage slot.
     * @notice The system fee is splitted between the onboarders and the investors.
     * @param sender User wishing to send funds to receiver, incurring the fee
     * @param receiver User receiving the funds
     * @param value Amount of tokens being transferred
     */
    function applyNetworkFee(address sender, address receiver, uint32 value) internal {
        Account account = accounts[hashFunc(sender, receiver)];
        int fee = calculateNetworkFee(int(value));
        if (sender < receiver) {
            account.feesOutstandingA += uint16(fee);
        } else {
            account.feesOutstandingB += uint16(fee);
        }

    }

    /*
     * @notice returns the linear interest on the imbalance since last account update.
     * @notice negative if A is indebted to B, positive otherwise
     */
    function occurredInterest(address sender, address receiver, uint16 mtime) public returns (int) {
        Account account = accounts[hashFunc(sender, receiver)];
        int elapsed = mtime - account.mtime;
        uint16 interest = 0;
        if (account.balanceAB > 0) { // netted balance, value B owes to A(if positive)
            interest = account.interestAB; // interest rate set by A for debt of B
        } else {
            interest = account.interestBA; // interest rate set by B for debt of A
        }
        return calculateInterest(interest, account.balanceAB) * elapsed;
    }

    /*
     * @notice Calculates the interest from the byte representation of annual interest rate
     * @param interest byte representation of annual interest rate
     * @param balance current balance value in the account
     */
    function calculateInterest(int interest, int balance) internal returns (int) {
        if(interest == 0 && interest > 255)
            return 0;
        return balance / (interest * 256);
    }

    /*
     * @notice Calculates the system fee from the value being transferred
     * @param value being transferred
     */
    function calculateNetworkFee(int value) internal returns (int) {
        return int(value / network_fee_divisor);
    }

    /*
     * @notice The fees deducted from the value while being transferred from second hop onwards in the mediated transfer
     */
    function deductedTransferFees(address sender, address receiver, int value) public returns (int) {
        return capacityFee(value) + imbalanceFee(sender, receiver, value);
    }

    /*
     * @notice reward for providing the edge with sufficient capacity
     * @notice beneficiary: sender (because receiver will receive if he's the next hop)
     */
    function capacityFee(int value) public returns (int) {
        return int(value / capacity_fee_divisor);
    }

    /*
     * @notice penality for increasing account imbalance
     * @notice beneficiary: sender (because receiver will receive if he's the next hop)
     * @notice NOTE: It should also incorporate the interest as users will favor being indebted in
     */
    function imbalanceFee(address sender, address receiver, int value) public returns (int) {
        Account account = accounts[hashFunc(sender, receiver)];
        int addedImbalance = 0;
        int newBalance = 0;
        if (sender < receiver) {
            // negative hence sender indebted to receiver so addedImbalace is the incoming value
            if (account.balanceAB <= 0) {
                addedImbalance = value;
            } else {
            // positive hence receiver indebted to sender so if the newBalance is smaller then zero we introduce imbalance
                newBalance = account.balanceAB - value;
                if (newBalance < 0)
                    addedImbalance = -newBalance;
            }
        } else {
            //sender address is greater, here semantics will be opposite of the one above
            // positive hence sender is indebted to receiver so addedImbalance is the incoming value
            if (account.balanceAB >= 0) {
                addedImbalance = value;
            } else {
            // negative hence receiver is indebted to the sender so if the newBalance is greater than zero we introduce imbalance
                newBalance = account.balanceAB + value;
                if(newBalance > 0)
                    addedImbalance = newBalance;
            }
        }
        return (addedImbalance / imbalance_fee_divisor);
    }

    /*
     * @notice Calculates the current modification day since system start.
     * @notice now is an alias for block.timestamp gives the epoch time of the current block.
     */
    function calculateMtime() public returns (uint mtime) {
        mtime = (now/(24*60*60)) - ((2016 - 1970)* 365);
    }

    /*
     * @notice Calculates the Imbalance fee
     * @param addedImbalance The imbalance introduced by the current value being transferred
     */
    function calculateImbalanceFee(int addedImbalance) public returns (int) {
        return (addedImbalance / imbalance_fee_divisor);
    }
    // Only test functions here will be removed in the final release
    function occurredInterestTest(address sender, address receiver, uint16 mtime) public returns (int, int) {
        Account account = accounts[hashFunc(sender, receiver)];
        int elapsed = mtime - account.mtime;
        uint16 di = 0;
        if (account.balanceAB > 0) {
            di = account.interestAB;
        } else {
            di = account.interestBA;
        }
        return (calculateInterest(di, account.balanceAB), elapsed);
    }

    function ByteInterestTest(address sender, address receiver, uint16 mtime) public returns (int, int, int) {
        Account account = accounts[hashFunc(sender, receiver)];
        uint16 di = 0;
        if (account.balanceAB > 0) {
            di = account.interestAB;
        }else{
            di = account.interestBA;
        }
        //calculateInterest(di, account.balanceAB)
        return (account.balanceAB, di, getBalance(sender, receiver));
    }

    function whichSmaller(address A, address B) public returns (string) {
        if (A < B) {
            return "A is smaller";
        }else{
            return "B is smaller";
        }
    }

    function testInterest(int di, int48 value, uint16 mtime) public returns (int) {
        int elapsed = mtime - uint16(0);
        return calculateInterest(di, value) * elapsed;
    }

    function test(int di, int value) public returns (int) {
        return value / (di*256);
    }

    function blockNumber() public returns (uint) {
        return block.number;
    }

    function blockTimestamp() public returns (uint epochtime) {
        return epochtime = now;
    }

}
