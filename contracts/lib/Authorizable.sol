pragma solidity ^0.5.8;


contract Authorizable {

    mapping (address => bool) public globalAuthorized;
    // mapping from user to mapping Address => isAuthorized
    mapping (address => mapping (address =>bool)) public authorized;

    event GlobalAuthorizedAddressAdd(address indexed target);
    event GlobalAuthorizedAddressRemove(address indexed target);

    event AuthorizedAddressAdd(address indexed target, address indexed sender);
    event AuthorizedAddressRemove(address indexed target, address indexed sender);

    /// @dev Authorizes an address.
    /// @param target Address to authorize.
    function addAuthorizedAddress(address target)
        public
    {
        authorized[msg.sender][target] = true;
        emit AuthorizedAddressAdd(target, msg.sender);
    }

    /// @dev Removes authorizion of an address.
    /// @param target Address to remove authorization from.
    function removeAuthorizedAddress(address target)
        public
    {
        delete authorized[msg.sender][target];
        emit AuthorizedAddressRemove(target, msg.sender);
    }

    /// @dev Authorizes an address.
    /// @param target Address to authorize.
    function addGlobalAuthorizedAddress(address target)
        internal
    {
        globalAuthorized[target] = true;
        emit GlobalAuthorizedAddressAdd(target);
    }

    /// @dev Removes authorizion of an address.
    /// @param target Address to remove authorization from.
    function removeGlobalAuthorizedAddress(address target)
        internal
    {
        delete globalAuthorized[target];
        emit GlobalAuthorizedAddressRemove(target);
    }
}
