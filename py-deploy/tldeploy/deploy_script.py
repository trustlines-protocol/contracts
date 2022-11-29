from dataclasses import dataclass
from unicodedata import name
from deploy_tools.cli import retrieve_private_key, connect_to_json_rpc
from deploy_tools.transact import wait_for_successful_function_call, send_transaction, build_transaction_options, wait_for_successful_transaction_receipts

from web3 import Account, Web3

from tldeploy.core import NetworkSettings, deploy_currency_network_proxy, deploy_network, verify_owner_not_deployer, deploy_beacon
from tldeploy.load_contracts import get_contract_interface

keystore_path = "/Users/oizo/code/tl-protocol/contracts/deployer_keystore.json"
private_key = retrieve_private_key(keystore_path)
account = Account.from_key(private_key)

owner_keystore_path = "/Users/oizo/code/tl-protocol/contracts/owner_keystore.json"
owner_key = retrieve_private_key(owner_keystore_path)
owner_account = Account.from_key(owner_key)

# web3_tlbc = connect_to_json_rpc("https://sepolia.infura.io/v3/6c6331474e1e4e93b087e8dc992c6e0a")
web3_tlbc = connect_to_json_rpc("http://127.0.0.1:8546/")
# web3_xdai = connect_to_json_rpc("https://goerli.infura.io/v3/6c6331474e1e4e93b087e8dc992c6e0a")
web3_xdai = connect_to_json_rpc("http://127.0.0.1:8545/")
verify_owner_not_deployer(web3_xdai, private_key=private_key, owner_address=owner_account.address)


def increase_nonce_to(web3: Web3, to_nonce: int):
    current_nonce = web3.eth.get_transaction_count(account.address)
    assert current_nonce <= to_nonce, "Cannot increase nonce to lower than current"

    to_increase = to_nonce - current_nonce
    tx_hashs = set()

    for i in range(to_increase):
        if i % 50 == 0 and i != 0:
             wait_for_successful_transaction_receipts(web3, tx_hashs)
             tx_hashs = set()

        transaction_options = build_transaction_options(
            gas=None, gas_price=None, nonce=current_nonce + i
        )

        transaction_options["to"] = account.address
        tx_hash = send_transaction(web3=web3, transaction_options=transaction_options, private_key=private_key)
        tx_hashs.add(tx_hash)

    wait_for_successful_transaction_receipts(web3, tx_hashs)
    assert web3.eth.get_transaction_count(account.address) == to_nonce, "Finish increasing nonce to wrong nonce"


def deploy_cn_v3():
    network_settings = NetworkSettings(
        name="implementationv3",
        symbol="impl",
    )

    contract = deploy_network(
        web3_xdai,
        network_settings,
        currency_network_contract_name="CurrencyNetworkOwnableV3",
        private_key=private_key,
    )
    print(f"Deployed currency network ownable v3 at address {contract.address}")
    return contract


def deploy_cn_v2():
    network_settings = NetworkSettings(
        name="implementationv3",
        symbol="impl",
    )

    contract = deploy_network(
        web3_xdai,
        network_settings,
        currency_network_contract_name="CurrencyNetworkOwnable",
        private_key=private_key,
    )
    print(f"Deployed currency network ownable v2 at address {contract.address}")
    return contract


def deploy_beacon_at_custom_address():
    beacon = deploy_beacon(
        web3_xdai,
        "0x3d494502d15E8eAE385fC86e116CD9Db6e4C38ec",  # old CN v2 address, used to deploy beacon at same address on xdai as tlbc
        owner_account.address,
        private_key=private_key,
    )
    print(f"Deployed beacon at address {beacon.address}")
    return beacon


def update_beacon_implementation(beacon, implementation_address):
    call = beacon.functions.upgradeTo(implementation_address)
    wait_for_successful_function_call(
        call,
        web3=web3_xdai,
        private_key=owner_key,
    )


currency_network_v3 = deploy_cn_v3()

increase_nonce_to(web3_xdai, 44)
currency_network_v2 = deploy_cn_v2()
assert currency_network_v2.address.lower() == "0x3d494502d15E8eAE385fC86e116CD9Db6e4C38ec".lower(), "Deployed CN v2 at wrong address"

increase_nonce_to(web3_xdai, 46)
beacon = deploy_beacon_at_custom_address()
assert beacon.address.lower() == "0xDEE27a84fB3Ef2be305b17b202D0b2E78B2e1252".lower(), "Deployed beacon at wrong address"
update_beacon_implementation(beacon, currency_network_v3.address)

@dataclass
class NetworkInfo:
    nonce: int
    expected_address: str

usd = NetworkInfo(nonce=50, expected_address="")

network_infos = [
    NetworkInfo(nonce=159, expected_address="0xdCBcdbA450eBAE81d99E8FC6B165a948D4ae5012"),
    NetworkInfo(nonce=269, expected_address="0x71Eb52d37fCB47a149Fb26232B67b9244A58FE6c"),
    NetworkInfo(nonce=978, expected_address="0x7AF4AcE4bdAe5918825Dc0eB22Bc4F67c69c645b"),    
    NetworkInfo(nonce=987, expected_address="0x9aBd28551C551Ac329dB9A25C59e3fB639A343BB"),    
    NetworkInfo(nonce=1000, expected_address="0xfbd90D5859Fad02b9Be55C706eBd052c52F8df21"),    
    NetworkInfo(nonce=1046, expected_address="0x9a7624dd0520F5F54a5B209cD93D7F7993c459ec"),    
    NetworkInfo(nonce=1052, expected_address="0x865cbDF17Fd3205E25369A079d7171466dC6c8cc"),    
    NetworkInfo(nonce=1058, expected_address="0x9b19Aa3a3938f3e9e24ded8a76c3fED2D2d5328c"),    
    NetworkInfo(nonce=1075, expected_address="0xd73E3db84e0EE4aB15D0144eF60764A1894dBD7c"),    
    NetworkInfo(nonce=1081, expected_address="0x66248105a7c96854eE9a0134Bb7657A4667cd8e9"),    
    NetworkInfo(nonce=1099, expected_address="0x96AF9CA9881c88456cABd0800b919Bc55778bFC4"),    
    NetworkInfo(nonce=1124, expected_address="0xff1FD88079eabA0e6F05Db99A602f70242F25349"),    
    NetworkInfo(nonce=1133, expected_address="0xEDE296b57824F4b1c24842c8f5c2AaBb56d23d65"),    
    NetworkInfo(nonce=1142, expected_address="0x553253115D0efa1BaBefdEd2a65C9E53CA8f7df6"),    
    NetworkInfo(nonce=1148, expected_address="0xCDd5371f67F65cD6D5ECcd0aBb62F423bABFb15A"),    
    NetworkInfo(nonce=1161, expected_address="0x7fFFa9096fCED0B26E6519B2037a9F045C21330d"),    
    NetworkInfo(nonce=1167, expected_address="0x2E72DB771cb4f70288e015dE36b78e269b3a6397"),    
    NetworkInfo(nonce=1176, expected_address="0x7E984f5B56B6272D1f41ad1372B129EAD550628C"),    
    NetworkInfo(nonce=1195, expected_address="0xd33FD4A1a96cf7d13b8E44A8e81b1e76f3ce92Ed"),    
    NetworkInfo(nonce=1211, expected_address="0x1Bf1e2bA541f36B6651ceFf2aCc53eCadf7c82E3"),    
    NetworkInfo(nonce=1217, expected_address="0xA6E914e1E7efB19D0c7894d6e561C26d96a45998"),    
    NetworkInfo(nonce=1237, expected_address="0xB447d648da8a780Ae8C837f726e601c7A43D4FFF"),    
    NetworkInfo(nonce=1277, expected_address="0x5Ff657c6aEf090ab7B761E2775EAd3e3fD3f96A1"),    
    NetworkInfo(nonce=1445, expected_address="0xEcA5A9BC6502c564d3F421EA0E05252f2252649a"),    
    NetworkInfo(nonce=1750, expected_address="0x35c2D7Ec13af15D6ED7a3eb1e5b911E419D9636d"),    
    NetworkInfo(nonce=2878, expected_address="0x56711Fd7e9D27490b356b217d7Fb589141b8f654"),    
    NetworkInfo(nonce=2887, expected_address="0xFab1BfDA181b998298D206Bd6EfB9CE7cd919f5F"),    
    NetworkInfo(nonce=2896, expected_address="0xC0F2EEc3a550248dd8BC24961cf323055b41b8BF"),    
    NetworkInfo(nonce=2908, expected_address="0xc1671Be60dB024e0eA2393D03F7E3905cEF75de2"),    
    NetworkInfo(nonce=2914, expected_address="0x1e3aD4E7f8375baD6e1322E3801487B7bb692830"),    
    NetworkInfo(nonce=2920, expected_address="0x59421C3664FaB317E26e8889a4a34ebA07384A9c"),    
    NetworkInfo(nonce=2939, expected_address="0x946b88048887Af4259A1cD6545eBB514d7cFD05F"),    
    NetworkInfo(nonce=2945, expected_address="0xBfA29944Fa6B7f06b084C2De943a5767159fc86e"),    
    NetworkInfo(nonce=2951, expected_address="0x40AD287A86051010FC46cC68674048cD1f1AF892"),    
    NetworkInfo(nonce=2957, expected_address="0x364B777CEF8c2E67c6a10c33BFc57c1c56EC5FFC"),    
    NetworkInfo(nonce=2968, expected_address="0x504be87de98C1E3A0494dF16B4327A74736126E5"),    
    NetworkInfo(nonce=2982, expected_address="0x0f7a5Edb2855C9208B260e7eF801dF9f5E79B8c3"),    
    NetworkInfo(nonce=2988, expected_address="0x11933E474C632D8a0CB69e2a86a761E627F75dEd"),    
    NetworkInfo(nonce=2994, expected_address="0x61963C98ee147c65BA4E630E09730bf90DBbB003"),    
    NetworkInfo(nonce=3011, expected_address="0xC8De4Ad7Cd5D0C0BFdCB2cd4a36E819F7bC70734"),    
    NetworkInfo(nonce=3020, expected_address="0xEcECf14185482071667ccCC5F823485CF18f5A83"),    
    NetworkInfo(nonce=3069, expected_address="0x7D31aE4D8D7bE97550968897F24060503C25F76c"),    
    NetworkInfo(nonce=3098, expected_address="0x9a24ff1377C785E82736285948a092c681ff6B45"),    
    NetworkInfo(nonce=3107, expected_address="0x7dAfA79fcfb8E23A96d564Ba762D7Efceff74Ebf"),    
    NetworkInfo(nonce=3125, expected_address="0xf5BB5C1DBdd0822d0Fa9E93e82B0cD0D0A388f51"),
]

for network_info in network_infos:
    increase_nonce_to(web3_xdai, network_info.nonce)
    old_network_interface = get_contract_interface("CurrencyNetworkV2")
    old_network = web3_tlbc.eth.contract(address = network_info.expected_address, abi=old_network_interface["abi"])
    network_settings = NetworkSettings(
        name=old_network.functions.name().call(),
        symbol=old_network.functions.symbol().call(),
        decimals=old_network.functions.decimals().call(),
        fee_divisor=old_network.functions.capacityImbalanceFeeDivisor().call(),
        default_interest_rate=old_network.functions.defaultInterestRate().call(),
        custom_interests=old_network.functions.customInterests().call(),
        prevent_mediator_interests=old_network.functions.preventMediatorInterests().call(),
        expiration_time=0,
    )

    contract = deploy_currency_network_proxy(
        web3=web3_xdai,
        network_settings=network_settings,
        beacon_address=beacon.address,
        owner_address=owner_account.address,
        private_key=private_key,
    )
    print(f"Deployed CN {network_settings.name} at address {contract.address}")
    assert contract.address.lower() == network_info.expected_address.lower(), "Deployed network at wrong address"
