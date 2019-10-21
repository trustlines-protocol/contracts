import json
from typing import Dict, Optional

import attr
import pkg_resources
from deploy_tools.compile import build_initcode
from deploy_tools.deploy import (
    increase_transaction_options_nonce,
    send_function_call_transaction,
)
from eth_keys.datatypes import PrivateKey
from hexbytes import HexBytes
from web3 import Web3
from web3.exceptions import BadFunctionCallOutput

from tldeploy.core import deploy, get_contract_interface
from tldeploy.signing import sign_msg_hash, solidity_keccak

MAX_GAS = 1_000_000


def validate_and_checksum_addresses(addresses):
    formatted_addresses = []
    for address in addresses:
        if Web3.isAddress(address):
            formatted_addresses.append(Web3.toChecksumAddress(address))
        else:
            raise ValueError(f"Given input {address} is not a valid address.")
    return formatted_addresses


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class MetaTransaction:

    from_: Optional[str] = None
    to: str
    value: int = 0
    data: bytes = bytes()
    fees: int = 0
    currency_network_of_fees: str = attr.ib()
    nonce: Optional[int] = None
    extra_data: bytes = bytes()
    signature: Optional[bytes] = None

    @currency_network_of_fees.default
    def default_for_currency_network_of_fees(self):
        return self.to

    @classmethod
    def from_function_call(
        cls,
        function_call,
        *,
        from_: str = None,
        to: str,
        nonce: int = None,
        fees: int = 0,
        currency_network_of_fees: str = None,
    ):
        """Construct a meta transaction from a web3 function call.

        Usage:
        `from_function_call(contract.functions.function())`
        """
        data = function_call.buildTransaction(transaction={"gas": MAX_GAS})["data"]

        if currency_network_of_fees is None:
            # Use default value for currency_network_of_fees
            return cls(from_=from_, to=to, value=0, data=data, fees=fees, nonce=nonce)
        else:
            return cls(
                from_=from_,
                to=to,
                value=0,
                data=data,
                fees=fees,
                currency_network_of_fees=currency_network_of_fees,
                nonce=nonce,
            )

    @property
    def hash(self) -> bytes:
        (from_, to, currency_network_of_fees) = validate_and_checksum_addresses(
            [self.from_, self.to, self.currency_network_of_fees]
        )
        return solidity_keccak(
            [
                "bytes1",
                "bytes1",
                "address",
                "address",
                "uint256",
                "bytes32",
                "uint64",
                "address",
                "uint256",
                "bytes",
            ],
            [
                "0x19",
                "0x00",
                from_,
                to,
                self.value,
                solidity_keccak(["bytes"], [self.data]),
                self.fees,
                currency_network_of_fees,
                self.nonce,
                self.extra_data,
            ],
        )

    def signed(self, key: PrivateKey) -> "MetaTransaction":
        return attr.evolve(self, signature=sign_msg_hash(self.hash, key=key))


class UnexpectedIdentityContractException(Exception):
    pass


class Delegate:
    def __init__(self, delegate_address: str, *, web3, identity_contract_abi):
        self.delegate_address = delegate_address
        self._web3 = web3
        self._identity_contract_abi = identity_contract_abi

    def estimate_gas_signed_meta_transaction(
        self, signed_meta_transaction: MetaTransaction
    ):
        return self._meta_transaction_function_call(
            signed_meta_transaction
        ).estimateGas({"from": self.delegate_address})

    def send_signed_meta_transaction(
        self, signed_meta_transaction: MetaTransaction, gas: int = MAX_GAS
    ) -> str:
        """
        Sends the meta transaction out inside of an ethereum transaction
        Returns: the hash of the envelop ethereum transaction
        """

        return self._meta_transaction_function_call(signed_meta_transaction).transact(
            {"from": self.delegate_address, "gas": gas}
        )

    def validate_meta_transaction(
        self, signed_meta_transaction: MetaTransaction
    ) -> bool:
        """Validates the fields of the meta transaction against the state of
        the identity contract.

        This is equivalent to ``` validate_replay_mechanism(tx)
        validate_signature(tx) Will raise
        UnexpectedIdentityContractException, if it could not find the
        check in the contract.
        """
        return self.validate_nonce(signed_meta_transaction) and self.validate_signature(
            signed_meta_transaction
        )

    def validate_nonce(self, signed_meta_transaction: MetaTransaction):
        """Validates the nonce by using the provided check by the identity
        contract.

        Returns: True, if the nonce was successfully validated, False if it was wrong
        Will raise UnexpectedIdentityContractException, if it could not find the check in the contract.
        """
        from_ = signed_meta_transaction.from_
        if from_ is None:
            raise ValueError("From has to be set")
        contract = self._get_identity_contract(from_)
        try:
            nonce_valid = contract.functions.validateNonce(
                signed_meta_transaction.nonce, signed_meta_transaction.hash
            ).call()
        except BadFunctionCallOutput:
            raise UnexpectedIdentityContractException(
                "validateNonce function not found"
            )

        return nonce_valid

    def validate_signature(self, signed_meta_transaction: MetaTransaction):
        """Validates the signature by using the provided check by the identity
        contract.

        Returns: True, if the signature was successfully validated, False if it was wrong
        Will raise UnexpectedIdentityContractException, if it could not find the check in the contract.
        """
        from_ = signed_meta_transaction.from_
        if from_ is None:
            raise ValueError("From has to be set")

        contract = self._get_identity_contract(from_)
        try:
            signature_valid = contract.functions.validateSignature(
                signed_meta_transaction.hash, signed_meta_transaction.signature
            ).call()
        except BadFunctionCallOutput:
            raise UnexpectedIdentityContractException(
                "validateSignature function not found"
            )

        return signature_valid

    def get_next_nonce(self, identity_address: str):
        """Returns the next usable nonce.

        Will raise UnexpectedIdentityContractException, if  it could not
        find the necessary function in the contract.
        """
        contract = self._get_identity_contract(identity_address)
        try:
            next_nonce = contract.functions.lastNonce().call() + 1
        except BadFunctionCallOutput:
            raise UnexpectedIdentityContractException("lastNonce function not found")
        return next_nonce

    def _get_identity_contract(self, address: str):
        return self._web3.eth.contract(abi=self._identity_contract_abi, address=address)

    def _meta_transaction_function_call(self, signed_meta_transaction: MetaTransaction):
        from_ = signed_meta_transaction.from_
        if from_ is None:
            raise ValueError("From has to be set")
        contract = self._get_identity_contract(from_)

        return contract.functions.executeTransaction(
            signed_meta_transaction.from_,
            signed_meta_transaction.to,
            signed_meta_transaction.value,
            signed_meta_transaction.data,
            signed_meta_transaction.fees,
            signed_meta_transaction.currency_network_of_fees,
            signed_meta_transaction.nonce,
            signed_meta_transaction.extra_data,
            signed_meta_transaction.signature,
        )


class Identity:
    def __init__(self, *, contract, owner_private_key: PrivateKey):
        self.contract = contract
        self._owner_private_key = owner_private_key

    @property
    def address(self):
        return self.contract.address

    def defaults_filled(self, meta_transaction: MetaTransaction) -> MetaTransaction:
        """Returns a meta transaction where the from field of the transaction
        is set to the identity address, and the nonce if not set yet is set to
        the next nonce."""

        meta_transaction = attr.evolve(meta_transaction, from_=self.address)

        if meta_transaction.nonce is None:
            meta_transaction = attr.evolve(
                meta_transaction, nonce=self.get_next_nonce()
            )

        return meta_transaction

    def signed_meta_transaction(
        self, meta_transaction: MetaTransaction
    ) -> MetaTransaction:
        return meta_transaction.signed(self._owner_private_key)

    def filled_and_signed_meta_transaction(
        self, meta_transaction: MetaTransaction
    ) -> MetaTransaction:
        meta_transaction = self.defaults_filled(meta_transaction)
        meta_transaction = self.signed_meta_transaction(meta_transaction)
        return meta_transaction

    def get_next_nonce(self):
        return self.contract.functions.lastNonce().call() + 1


def get_pinned_proxy_interface():
    with open(pkg_resources.resource_filename(__name__, "identity-proxy.json")) as file:
        return json.load(file)["Proxy"]


def deploy_identity_proxy_factory(
    *, web3: Web3, transaction_options: Dict = None, private_key: bytes = None
):
    if transaction_options is None:
        transaction_options = {}

    identity_proxy_factory = deploy(
        "IdentityProxyFactory",
        web3=web3,
        transaction_options=transaction_options,
        private_key=private_key,
    )
    increase_transaction_options_nonce(transaction_options)
    return identity_proxy_factory


def deploy_identity_implementation(
    *, web3: Web3, transaction_options: Dict = None, private_key: bytes = None
):
    if transaction_options is None:
        transaction_options = {}

    indentity_implementation = deploy(
        "Identity",
        web3=web3,
        transaction_options=transaction_options,
        private_key=private_key,
    )
    increase_transaction_options_nonce(transaction_options)
    return indentity_implementation


def deploy_proxied_identity(web3, factory_address, implementation_address, signature):
    owner = recover_proxy_deployment_signature_owner(
        web3, factory_address, implementation_address, signature
    )

    interface = get_pinned_proxy_interface()
    initcode = build_initcode(
        contract_abi=interface["abi"],
        contract_bytecode=interface["bytecode"],
        constructor_args=[owner],
    )

    factory_interface = get_contract_interface("IdentityProxyFactory")
    factory = web3.eth.contract(address=factory_address, abi=factory_interface["abi"])

    function_call = factory.functions.deployProxy(
        initcode, implementation_address, signature
    )
    receipt = send_function_call_transaction(function_call, web3=web3)

    deployment_event = factory.events.ProxyDeployment().processReceipt(receipt)
    proxy_address = HexBytes(deployment_event[0]["args"]["proxyAddress"])

    computed_proxy_address = build_create2_address(factory_address, initcode)
    assert (
        computed_proxy_address == proxy_address
    ), "The computed proxy address does not match the deployed address found via events"

    identity_interface = get_contract_interface("Identity")
    proxied_identity = web3.eth.contract(
        address=proxy_address,
        abi=identity_interface["abi"],
        bytecode=identity_interface["bytecode"],
    )
    return proxied_identity


def recover_proxy_deployment_signature_owner(
    web3, factory_address, implementation_address, signature
):
    abi_types = ["bytes1", "bytes1", "address", "address"]
    signed_values = ["0x19", "0x00", factory_address, implementation_address]
    signed_hash = Web3.solidityKeccak(abi_types, signed_values)
    owner = web3.eth.account.recoverHash(signed_hash, signature=signature)
    return owner


def build_create2_address(deployer_address, bytecode, salt="0x" + "00" * 32):
    hashed_bytecode = Web3.solidityKeccak(["bytes"], [bytecode])
    to_hash = ["0xff", deployer_address, salt, hashed_bytecode]
    abi_types = ["bytes1", "address", "bytes32", "bytes32"]

    return Web3.solidityKeccak(abi_types, to_hash)[12:]
