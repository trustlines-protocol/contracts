pragma solidity ^0.8.0;

/**
 * CurrencyNetwork
 *
 * Adds onboarding functionality to a basic currency network
 *
 **/
contract Onboarding {
    // map each user to its onboarder
    mapping(address => address) public onboarder;
    // value in the mapping for users that do not have an onboarder
    address constant NO_ONBOARDER = address(1);

    event Onboard(address indexed _onboarder, address indexed _onboardee);

    function _applyOnboardingRules(address a, address b) internal {
        if (onboarder[a] == address(0)) {
            if (onboarder[b] == address(0)) {
                onboarder[a] = NO_ONBOARDER;
                onboarder[b] = NO_ONBOARDER;
                emit Onboard(NO_ONBOARDER, a);
                emit Onboard(NO_ONBOARDER, b);
                return;
            } else {
                onboarder[a] = b;
                emit Onboard(b, a);
            }
        } else {
            if (onboarder[b] == address(0)) {
                onboarder[b] = a;
                emit Onboard(a, b);
            }
        }
    }
}

// SPDX-License-Identifier: MIT
