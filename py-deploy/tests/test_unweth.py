import pytest
from tldeploy.core import deploy
import eth_tester.exceptions


@pytest.fixture()
def unweth_contract(web3):
    return deploy("UnwEth", web3)


def test_transfer(unweth_contract, web3, accounts):
    A, B, *rest = accounts

    wei = 10000
    assert web3.eth.getBalance(A) > wei
    receiver_wei_before = web3.eth.getBalance(B)

    web3.eth.sendTransaction(
        {
            'from': A,
            'to': unweth_contract.address,
            'value': wei
        })

    unweth_contract.transact({'from': A}).transfer(B, wei)

    assert web3.eth.getBalance(B) == receiver_wei_before + wei


def test_deposit_withdraw(unweth_contract, web3, accounts):
    _, A, *rest = accounts

    wei = 10**18
    balance = web3.eth.getBalance(A)

    print(web3.eth.getBalance(A))

    unweth_contract.transact({'from': A, 'value': wei}).deposit()
    print(web3.eth.getBalance(A))
    print(balance-web3.eth.getBalance(A)-wei)

    assert web3.eth.getBalance(A) == pytest.approx(balance - wei, abs=100000)  # approx, because ot gas costs
    assert unweth_contract.call().balanceOf(A) == wei

    unweth_contract.transact({'from': A}).withdraw(wei)
    assert web3.eth.getBalance(A) == pytest.approx(balance, abs=100000)  # approx, because ot gas costs


def test_transfer_from(unweth_contract, web3, accounts):
    A, B, C, *rest = accounts
    wei = 10 ** 18

    balance = web3.eth.getBalance(B)
    unweth_contract.transact({'from': A, 'value': wei}).deposit()

    with pytest.raises(eth_tester.exceptions.TransactionFailed):
        unweth_contract.transact({'from': C}).transferFrom(A, B, wei)

    unweth_contract.transact().addAuthorizedAddress(C)
    unweth_contract.transact({'from': C}).transferFrom(A, B, wei)

    assert web3.eth.getBalance(B) == balance + wei
