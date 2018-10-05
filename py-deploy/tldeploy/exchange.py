from tldeploy.signing import keccak256, eth_sign


class Order(object):

    def __init__(
        self,
        exchange_address,
        maker_address,
        taker_address,
        maker_token,
        taker_token,
        fee_recipient,
        maker_token_amount,
        taker_token_amount,
        maker_fee,
        taker_fee,
        expiration_timestamp_in_sec,
        salt
    ):
        self.exchange_address = exchange_address
        self.maker_address = maker_address
        self.taker_address = taker_address
        self.maker_token = maker_token
        self.taker_token = taker_token
        self.fee_recipient = fee_recipient
        self.maker_token_amount = maker_token_amount
        self.taker_token_amount = taker_token_amount
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.expiration_timestamp_in_sec = expiration_timestamp_in_sec
        self.salt = salt

    def hash(self):
        return keccak256(
            self.exchange_address,
            self.maker_address,
            self.taker_address,
            self.maker_token,
            self.taker_token,
            self.fee_recipient,
            self.maker_token_amount,
            self.taker_token_amount,
            self.maker_fee,
            self.taker_fee,
            self.expiration_timestamp_in_sec,
            self.salt
        )

    def sign(self, key):
        return eth_sign(self.hash(), key)
