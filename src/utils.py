import yaml, asyncio, websockets, json, hmac, hashlib
import requests
import pandas as pd
from pathlib import Path
from time import sleep
from datetime import datetime
from pybit.unified_trading import HTTP


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
    path = "sessions.yaml"
    uri = "wss://stream.bybit.com/v5/private"
    
    def __init__(self, username, api_key, api_secret) -> None:
        self.username = username
        self.api_key = api_key
        self.api_secret = api_secret
        self.obj = self.load_sessions()

    @classmethod
    def load_sessions(cls):
        if not Path(cls.path).is_file():
            open(cls.path, "x")
        with open(cls.path, "r") as stream:
            obj = yaml.safe_load(stream)
        if obj == None: obj = {}
        return obj

    def save(self):
        self.obj[self.username] = {
            "key": self.api_key,
            "secret": self.api_secret
        }
        with open(self.path, "w", encoding="utf8") as stream:
            yaml.dump(self.obj, stream, default_flow_style=False, allow_unicode=True)

    def remove(self):
        self.obj.pop(self.username, None)
        with open(self.path, "w", encoding="utf8") as stream:
            yaml.dump(self.obj, stream, default_flow_style=False, allow_unicode=True)

    def query_coin_balance(self):
        session = HTTP(
            api_key=self.api_key,
            api_secret=self.api_secret,
        )
        self.unified = session.get_coins_balance(accountType="UNIFIED")
        self.fund = session.get_coins_balance(accountType="FUND")

    async def authenticate(self):
        api_key = self.api_key
        api_secret = self.api_secret
        expires = int((datetime.now().timestamp() + 10) * 1000)  # Expires in 10 seconds
        signature = hmac.new(api_secret.encode(), f'GET/realtime{expires}'.encode(), hashlib.sha256).hexdigest()

        auth_msg = {
            "reqId": "auth",
            "op": "auth",
            "args": [api_key, expires, signature]
        }

        self.ws = await websockets.connect(self.uri)
        await self.ws.send(json.dumps(auth_msg))
        response = await self.ws.recv()
        return json.loads(response)

    async def send_subscription(self, topic):
        sub_msg = {
            "op": "subscribe",
            "args": [topic]
        }

        await self.ws.send(json.dumps(sub_msg))
        print(f"Subscription message for user {self.username} sent.")

    async def keep_alive(self):
        while True:
            await self.ws.send(json.dumps({'op': 'ping'}))
            await asyncio.sleep(10)  # Sleep for 10 seconds

    async def listen_messages(self, bot, chat_id):
        while True:
            message = await self.ws.recv()
            resp = json.loads(message)
            # if resp.get('op', None) not in ['pong', 'subscribe']:
            if resp.get('op', None) not in ['pong']:
                await bot.send_message(chat_id, text = f"Message received: {message}")

    async def subcribe_wallet_stream(self, bot, chat_id):
        try:
            await self.send_subscription('wallet')
            listen_task = asyncio.create_task(self.listen_messages(bot, chat_id))
            ping_task = asyncio.create_task(self.keep_alive())
            await asyncio.gather(listen_task, ping_task, return_exceptions=True)
        except Exception as e:
            await bot.send_message(chat_id, text = f"Error: {e}")


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
    sessions = BybitAccount.load_sessions()
    username = 'testwallet'
    key = sessions[username]['key']
    # key = "abc"
    secret = sessions[username]['secret']
    # print(username, key, secret)
    account = BybitAccount(username, key, secret)
    # account.save()
    # account.remove()

    # async def test():
    #     resp = await account.authenticate()
    #     if resp["success"]:
    #         await account.subcribe_wallet_stream()
    #     else:
    #         print("Authentication Failure")

    # asyncio.run(test())

    # asyncio.new_event_loop().run_until_complete(account.send_subscription('wallet'))
    # asyncio.run(account.subcribe_wallet_stream())
    # asyncio.run(account.subcribe_wallet_stream())
    # account.subcribe_wallet_stream()
    
    account.query_coin_balance()
    print(account.unified)
    print(account.fund)
