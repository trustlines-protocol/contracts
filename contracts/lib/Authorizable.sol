pragma solidity ^0.8.0;

contract Authorizable {
    mapping(address => bool) public globalAuthorized;
    // mapping from user to mapping Address => isAuthorized
    mapping(address => mapping(address => bool)) public authorizedBy;

    event GlobalAuthorizedAddressAdd(address indexed authorized);
    event GlobalAuthorizedAddressRemove(address indexed authorized);

    event AuthorizedAddressAdd(
        address indexed authorized,
        address indexed allower
    );
    event AuthorizedAddressRemove(
        address indexed authorized,
        address indexed allower
    );

    /// @dev Authorizes an address.
    /// @param target Address to authorize.
    function addAuthorizedAddress(address target) public virtual {
        authorizedBy[msg.sender][target] = true;
        emit AuthorizedAddressAdd(target, msg.sender);
    }

    /// @dev Removes authorizion of an address.
    /// @param target Address to remove authorization from.
    function removeAuthorizedAddress(address target) public {
        require(
            authorizedBy[msg.sender][target],
            "Target not authorized by sender."
        );
        delete authorizedBy[msg.sender][target];
        emit AuthorizedAddressRemove(target, msg.sender);
    }

    /// @dev Authorizes an address.
    /// @param target Address to authorize.
    function addGlobalAuthorizedAddress(address target) internal {
        globalAuthorized[target] = true;
        emit GlobalAuthorizedAddressAdd(target);
    }

    /// @dev Removes authorizion of an address.
    /// @param target Address to remove authorization from.
    function removeGlobalAuthorizedAddress(address target) internal {
        require(globalAuthorized[target], "Target not global authorized.");
        delete globalAuthorized[target];
        emit GlobalAuthorizedAddressRemove(target);
    }
}

// SPDX-License-Identifier: MIT
