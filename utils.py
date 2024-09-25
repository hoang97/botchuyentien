import yaml


class Config:
    path = "settings.yaml"

    def read(self):
        with open(self.path, "r") as stream:
            self.obj = yaml.safe_load(stream)
        
    def update(self, data):
        with open(self.path, "w", encoding="utf8") as stream:
            yaml.dump(data, stream, default_flow_style=False, allow_unicode=True)


class BybitAccount:
    api_token = ""

    pass


class BybitP2P:
    cookie = ""
    api_url = "https://api2.bybit.com/fiat/otc/item/online"

    def _get_buy_offer(self):
        pass

    def _get_sell_offer(self):
        pass

if __name__ == "__main__":
    config = Config()
    config.read()
    print(config.obj)
    config.update({'a': 456})
    config.read()
    print(config.obj)
