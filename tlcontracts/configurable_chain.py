from populus.chain import ExternalChain


class ConfigurableChain(ExternalChain):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._web3_config = None

    @classmethod
    def from_chain(cls, chain):
        return cls(chain.project, chain.chain_name, chain.config)

    def get_web3_config(self):
        if self._web3_config is None:
            self._web3_config = self.config.get_web3_config()
        return self._web3_config

    def set_json_rpc(self, jsonrpc):
        self.web3_config['provider.settings'] = {
            "endpoint_uri": jsonrpc
        }
