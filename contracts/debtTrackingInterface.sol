pragma solidity ^0.5.8;


interface debtTrackingInterface {

    event DebtUpdate(address _debtor, address _creditor, int72 _newDebt);

    function increaseDebt(address creditor, uint64 value) external;

    function getDebt(address debtor, address creditor) external view returns (int256);
}
