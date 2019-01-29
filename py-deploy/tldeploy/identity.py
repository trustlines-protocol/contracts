from eth_keys.datatypes import PrivateKey
from tldeploy.signing import solidity_keccak, sign_msg_hash


class MetaTransaction():

    def __init__(
        self,
        *,
        from_: str = None,
        to: str,
        value: int = 0,
        data: bytes = bytes(),
        nonce: int = None,
        extra_hash: bytes = bytes(),
        signature: bytes = None,
    ):
        self.from_ = from_
        self.to = to
        self.value = value
        self.data = data
        self.nonce = nonce
        self.extra_hash = extra_hash
        self.signature = signature

    @classmethod
    def from_function_call(
        cls,
        to: str,
        function_call,
        *,
        nonce: int = None,
        from_: int = None,
    ):
        data = function_call.buildTransaction(transaction={'gas': 1_000_000})['data']

        return cls(
            from_=from_,
            to=to,
            value=0,
            data=data,
            nonce=nonce,
        )

    @property
    def hash(self) -> bytes:
        return solidity_keccak(
            [
                'bytes1',
                'bytes1',
                'address',
                'address',
                'uint256',
                'bytes32',
                'uint256',
                'bytes',
            ],
            [
                '0x19',
                '0x00',
                self.from_,
                self.to,
                self.value,
                solidity_keccak(['bytes'], [self.data]),
                self.nonce,
                self.extra_hash,
            ]
        )

    def sign(self, key: PrivateKey):
        self.signature = sign_msg_hash(self.hash, key=key)

    def __repr__(self):
        return 'MetaTransaction(from_={from_}, to={to}, value={value}, ' \
               'data={data}, nonce={nonce}, extra_hash={extra_hash}, signature={signature})'.format(
                from_=self.from_,
                to=self.to,
                value=self.value,
                data=self.data,
                nonce=self.nonce,
                extra_hash=self.extra_hash,
                signature=self.signature,
                )


class IdentityContractProxy:

    def __init__(
        self,
        contract,
        delegator,
        private_key: PrivateKey = None
    ):
        self.contract = contract
        self.private_key = private_key
        self.delegator = delegator

    @property
    def address(self):
        return self.contract.address

    def fill_defaults(
        self,
        meta_transaction: MetaTransaction,
    ):

        if meta_transaction.from_ is None:
            meta_transaction.from_ = self.address

        if meta_transaction.nonce is None:
            meta_transaction.nonce = self.get_next_nonce()

    def send_signed_transaction(
        self,
        signed_meta_transaction: MetaTransaction
    ):

        self.contract.functions.executeTransaction(
            signed_meta_transaction.from_,
            signed_meta_transaction.to,
            signed_meta_transaction.value,
            signed_meta_transaction.data,
            signed_meta_transaction.nonce,
            signed_meta_transaction.extra_hash,
            signed_meta_transaction.signature,
        ).transact({'from': self.delegator})

    def send_transaction(
        self,
        meta_transaction: MetaTransaction,
    ):
        if self.private_key is None:
            raise ValueError('No private key set')

        self.fill_defaults(meta_transaction)
        meta_transaction.sign(self.private_key)

        self.send_signed_transaction(meta_transaction)

    def get_next_nonce(self):
        return 0
