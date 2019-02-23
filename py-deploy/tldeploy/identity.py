from typing import Optional

import attr
from eth_keys.datatypes import PrivateKey
from tldeploy.signing import solidity_keccak, sign_msg_hash
from web3.exceptions import BadFunctionCallOutput

MAX_GAS = 1_000_000


@attr.s(auto_attribs=True, kw_only=True, frozen=True)
class MetaTransaction:

    from_: Optional[str] = None
    to: str
    value: int = 0
    data: bytes = bytes()
    nonce: Optional[int] = None
    extra_data: bytes = bytes()
    signature: Optional[bytes] = None

    @classmethod
    def from_function_call(
        cls, function_call, *, from_: str = None, to: str, nonce: int = None
    ):
        """Construct a meta transaction from a web3 function call

        Usage:
        `from_function_call(contract.functions.function()`
        """
        data = function_call.buildTransaction(transaction={"gas": MAX_GAS})["data"]

        return cls(from_=from_, to=to, value=0, data=data, nonce=nonce)

    @property
    def hash(self) -> bytes:
        return solidity_keccak(
            [
                "bytes1",
                "bytes1",
                "address",
                "address",
                "uint256",
                "bytes32",
                "uint256",
                "bytes",
            ],
            [
                "0x19",
                "0x00",
                self.from_,
                self.to,
                self.value,
                solidity_keccak(["bytes"], [self.data]),
                self.nonce,
                self.extra_data,
            ],
        )

    def signed(self, key: PrivateKey) -> "MetaTransaction":
        return attr.evolve(self, signature=sign_msg_hash(self.hash, key=key))


class UnexpectedIdentityContractException(Exception):
    pass


class Delegator:
    def __init__(self, delegator_address: str, *, web3, identity_contract_abi):
        self.delegator_address = delegator_address
        self._web3 = web3
        self._identity_contract_abi = identity_contract_abi

    def estimate_gas_signed_meta_transaction(
        self, signed_meta_transaction: MetaTransaction
    ):
        return self._meta_transaction_function_call(
            signed_meta_transaction
        ).estimateGas({"from": self.delegator_address})

    def send_signed_meta_transaction(
        self, signed_meta_transaction: MetaTransaction, gas: int = MAX_GAS
    ) -> str:
        """
        Sends the meta transaction out inside of a ethereum transaction
        Returns: the hash of the envelop ethereum transaction

        """
        return self._meta_transaction_function_call(signed_meta_transaction).transact(
            {"from": self.delegator_address, "gas": gas}
        )

    def validate_meta_transaction(
        self, signed_meta_transaction: MetaTransaction
    ) -> bool:
        """
        Validates the fields of the meta transaction against the state of the identity contract

        This is equivalent to
        ```
        validate_replay_mechanism(tx)
        validate_signature(tx)
        Will raise UnexpectedIdentityContractException, if it could not find the check in the contract.
        """
        return self.validate_nonce(signed_meta_transaction) and self.validate_signature(
            signed_meta_transaction
        )

    def validate_nonce(self, signed_meta_transaction: MetaTransaction):
        """
        Validates the nonce by using the provided check by the identity contract

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
        """
        Validates the signature by using the provided check by the identity contract

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
        """
        Returns the next usable nonce

        Will raise UnexpectedIdentityContractException, if  it could not find the necessary function in the contract.
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
        """
        Returns a meta transaction where the from field of the transaction is set to the identity address,
        and the nonce if not set yet is set to the next nonce
        """

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
