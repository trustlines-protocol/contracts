import subprocess
from time import sleep

import pytest
from populus import Project

from tlcontracts.deploy import deploy_networks, deploy_test_network


@pytest.fixture(autouse=True, scope='session')
def blockchain():
    p = subprocess.Popen('testrpc-py')
    sleep(3)  # give it some time to set up
    yield
    p.terminate()


@pytest.fixture(scope='session')
def project():
    return Project()


def test_deploy_networks(project):
    chain_name = 'testrpclocal'

    networks = [('Euro', 'EUR', 2), ('US Dollar', 'USD', 2), ('Testcoin', 'T', 6)]

    networks, exchange, unw_eth = deploy_networks(chain_name, networks, project)

    assert networks[0].call().name() == 'Euro'
    assert unw_eth.call().decimals() == 18


def test_deploy_network(project):
    chain_name = 'testrpclocal'

    network = deploy_test_network(chain_name, project)

    assert network.call().name() == 'Trustlines'
