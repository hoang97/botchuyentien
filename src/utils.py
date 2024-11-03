import yaml
import requests
import pandas as pd


def add_profit(rate, profit):
    return rate * (1 - profit/100)

def get_rate(profit, base_rate, vnd_min, vnd_max, rub_min, rub_max, market_vnd, market_rub):
    rate = add_profit(base_rate, profit)
    rate_not_in_range = (vnd_max*rate < rub_min) | (vnd_min*rate > rub_max)
    if rate_not_in_range:
        return None
    else:
        base_vnd = market_vnd
        if base_vnd*rate < rub_min:
            base_vnd = vnd_max
        elif base_vnd*rate > rub_max:
            base_vnd = vnd_min
        base_rub = base_vnd*rate
        return [base_vnd + 300, base_rub, base_vnd, base_rub]
        

class Config:
    path = "settings.yaml"

    def __init__(self):
        self.reload()

    def reload(self):
        with open(self.path, "r") as stream:
            self.obj = yaml.safe_load(stream)
        self.bybit_cookie = self.obj['_BYBIT_COOKIE']
        self.tele_token = self.obj['_TELE_TOKEN']
        self.list_admin = self.obj['_LIST_ADMIN']
        self.tele_channel = self.obj['_TELE_CHANNEL']
        self.tele_admin_group = self.obj['_TELE_ADMIN_GROUP']
        self.profit_percent = self.obj['PROFIT_PERCENT']
        self.vnd_min = self.obj['VND_MIN']
        self.vnd_max = self.obj['VND_MAX']
        self.rub_min = self.obj['RUB_MIN']
        self.rub_max = self.obj['RUB_MAX']
        self.market_vnd = self.obj['MARKET_VND']
        self.market_rub = self.obj['MARKET_RUB']
        
    def save(self):
        with open(self.path, "w", encoding="utf8") as stream:
            yaml.dump(self.obj, stream, default_flow_style=False, allow_unicode=True)
        self.reload()

    def update(self, key, value):
        self.obj[key] = value
        self.save()


class BybitAccount:
    api_token = ""

    pass


class BybitP2P:
    cookie = ""
    api_url = "https://api2.bybit.com/fiat/otc/item/online"

    def __init__(self, cookie) -> None:
        self.cookie = cookie

    def get_offer(self, side, tokenId, currencyId, size):
        r"""Return P2P offers.

        :param side: 0 (buy) or 1(sell)
        :param tokenId: ID của token muốn mua hoặc bán (USDT, ETH, BTC, ...)
        :param currencyId: IDvnd_min của tiền mặt (VND, RUB, ...)
        :return: offers: Danh sách các P2P offers
        """
        data = {
            "tokenId": tokenId,
            "currencyId": currencyId,
            "side": str(side),
            "size": str(size),
            "page": "1"
        }
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "Cookie": self.cookie,
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
        }
        r = requests.post(url=self.api_url, json=data, headers=headers)
        return r.json()
    
    def get_detail_rate(self):
        columns = ["nickName", "price", "payments", "recentOrderNum", "recentExecuteRate", "minAmount", "maxAmount"]
        float_columns = ["price", "recentOrderNum", "recentExecuteRate", "minAmount", "maxAmount"]
        USDT_VND = pd.DataFrame(self.get_offer(0, "USDT", "VND", 100)['result']['items'])
        RUB_USDT = pd.DataFrame(self.get_offer(1, "USDT", "RUB", 100)['result']['items'])
        USDT_VND = USDT_VND[columns]
        RUB_USDT = RUB_USDT[columns]
        USDT_VND[float_columns] = USDT_VND[float_columns].astype(float)
        RUB_USDT[float_columns] = RUB_USDT[float_columns].astype(float)

        USDT_VND = USDT_VND[(USDT_VND['recentOrderNum'] > 50) & (USDT_VND['recentExecuteRate'] > 90)]
        RUB_USDT = RUB_USDT[(RUB_USDT['recentOrderNum'] > 30) & (RUB_USDT['recentExecuteRate'] > 90)]

        vnd = USDT_VND['price'].astype(float).quantile(0.75)
        rub = RUB_USDT['price'].astype(float).quantile(0.75)

        return [rub, vnd, USDT_VND.head(3), RUB_USDT.head(3)]
    
    def get_exchange_rate(self):
        [rub, vnd, _, _] = self.get_detail_rate()
        return rub/vnd


if __name__ == "__main__":
    config = Config()
    # print(config.obj)
    # config.update({'a': 456})
    # config.reload()
    # print(config.obj)
    p2p = BybitP2P(config.bybit_cookie)
    # offers = p2p.get_offer(0, 'USDT', 'VND', 100)
    # print(offers)
    [_, _, vnd2usdt, usdt2rub] = p2p.get_detail_rate()
    print(vnd2usdt)
    print(usdt2rub)
