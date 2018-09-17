import pytest
from ethereum import tester


@pytest.fixture()
def unweth_contract(chain):
    UnwEthFactory = chain.provider.get_contract_factory('UnwEth')
    deploy_txn_hash = UnwEthFactory.deploy(args=[])
    contract_address = chain.wait.for_contract_address(deploy_txn_hash)
    contract = UnwEthFactory(address=contract_address)

    return contract


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

    with pytest.raises(tester.TransactionFailed):
        unweth_contract.transact({'from': C}).transferFrom(A, B, wei)

    unweth_contract.transact().addAuthorizedAddress(C)
    unweth_contract.transact({'from': C}).transferFrom(A, B, wei)

    assert web3.eth.getBalance(B) == balance + wei
