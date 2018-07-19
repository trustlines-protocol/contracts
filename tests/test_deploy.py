import subprocess
from time import sleep

import pytest
from populus import Project

from tlcontracts.deploy import deploy_networks, deploy_network


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
    chain = project.get_chain('testrpclocal')

    networks = [('Fugger', 'FUG', 2), ('Hours', 'HOU', 2), ('Testcoin', 'T', 6)]
    with chain:
        networks, exchange, unw_eth = deploy_networks(chain, networks)

    assert networks[0].call().name() == 'Fugger'
    assert unw_eth.call().decimals() == 18


def test_deploy_network(project):
    with project.get_chain('testrpclocal') as chain:
        network = deploy_network(chain, 'Testcoin', 'T', 2)

    assert network.call().name() == 'Testcoin'
