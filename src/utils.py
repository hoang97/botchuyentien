import yaml
import requests
import pandas as pd
import pygsheets
from pybit.unified_trading import HTTP


def add_profit(rate, profit):
    return rate * (1 - profit/100)
    
def get_changed_value(A, B):
    keys = set(A.keys())
    keys.union(set(B.keys()))
    changed_keys = {}
    for key in keys:
        x = float(A.get(key, 0.0))
        y = float(B.get(key, 0.0))
        if x != y:
            changed_keys[key] = y-x
    return changed_keys

def get_coin_from_response(resp):
    result = {}
    for item in resp["result"]["balance"]:
        result[item["coin"]] = item["walletBalance"]
    return result


class GoogleSheet:

    def __init__(self, name, cred_path) -> None:
        self.name = name
        self.cred_path = cred_path
        client = pygsheets.authorize(service_file=cred_path)
        self.wks = client.open(name).sheet1
    
    def insert_row(self, data):
        print(data)
        self.wks.append_table(values=data, overwrite=True)
        # self.wks.insert_rows(self.wks.rows, values=data, inherit=True)

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
    
    def __init__(self, username, api_key, api_secret) -> None:
        self.username = username
        self.api_key = api_key
        self.api_secret = api_secret
        self.query_coin_balance()

    def query_coin_balance(self):
        session = HTTP(
            api_key=self.api_key,
            api_secret=self.api_secret,
        )
        self.unified = get_coin_from_response(session.get_coins_balance(accountType="UNIFIED"))
        self.fund = get_coin_from_response(session.get_coins_balance(accountType="FUND"))

    def query_change_balance(self):
        prev_unified = self.unified
        prev_fund = self.fund
        self.query_coin_balance()
        return {
            "unified": get_changed_value(prev_unified, self.unified),
            "fund": get_changed_value(prev_fund, self.fund)
        }


class BybitP2P:
    cookie = ""
    api_url = "https://api2.bybit.com/fiat/otc/item/online"

    def __init__(self, cookie) -> None:
        self.cookie = cookie

    def get_offer(self, side, tokenId, currencyId, size):
        r"""Return P2P offers.

        :param side: 0 (buy) or 1(sell)
        :param tokenId: ID của token muốn mua hoặc bán (USDT, ETH, BTC, ...)
        :param currencyId: ID của tiền mặt (VND, RUB, ...)
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
    # config = Config()
    # print(config.obj)
    # config.update({'a': 456})
    # config.reload()
    # print(config.obj)
    # p2p = BybitP2P(config.bybit_cookie)
    # offers = p2p.get_offer(0, 'USDT', 'VND', 100)
    # print(offers)
    # [_, _, vnd2usdt, usdt2rub] = p2p.get_detail_rate()
    # print(vnd2usdt)
    # print(usdt2rub)

    # sessions = BybitAccount.load_sessions()
    # username = 'testwallet'
    # key = sessions[username]['key']
    # # key = "abc"
    # secret = sessions[username]['secret']
    # # print(username, key, secret)
    # account = BybitAccount(username, key, secret)
    # print(account.query_change_balance())

    ggsheet = GoogleSheet('bybit_accounts', 'cred.json')
    ggsheet.insert_row(['hoangdb1', 'nhận được', '100', 'USDT', 'FUNDING', '16/11/2024 10:10:10'])
    # ggsheet.insert_row([1,2,3,4,5])

