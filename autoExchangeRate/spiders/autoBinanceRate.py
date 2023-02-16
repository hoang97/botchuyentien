from copy import deepcopy
from gc import callbacks
import scrapy, telegram
import json, math
import xml.etree.ElementTree as ET


class AutobinancerateSpider(scrapy.Spider):
    name = 'autoBinanceRate'
    allowed_domains = ['p2p.binance.com', 'portal.vietcombank.com.vn', 'm.kovalut.ru']
    start_urls = ['https://m.kovalut.ru/kurs/sankt-peterburg']
    binance_api_url = 'https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search'
    vcb_api_url = 'https://portal.vietcombank.com.vn/Usercontrols/TVPortal.TyGia/pXML.aspx'

    bot_token = '5225045930:AAHo07BayUikgm2JHyS17ArY0iryUlkR7wI'
    bot = telegram.Bot(token=bot_token)

    def get_binanace_data(self, page, rows, asset, tradeType, fiat, callback):
        payload = {
            "page": page,
            "rows": rows,
            "asset": asset,
            "tradeType": tradeType,
            "fiat": fiat,
        }
        stringData = json.dumps(payload)
        headers = {
            "Content-Type": "application/json",
            "Content-Length": len(stringData),
        }

        return scrapy.Request(self.binance_api_url, callback=callback, method="POST", body=stringData, headers=headers, meta=payload)

    def get_VCB_data(self):
        return scrapy.Request(self.vcb_api_url, callback=self.parse_vcb_page)

    def parse(self, response):
        # lấy tỷ giá Binance
        yield self.get_binanace_data(1, 20, "USDT", "BUY", "RUB", self.parse_first_page)
        yield self.get_binanace_data(1, 20, "USDT", "SELL", "RUB", self.parse_first_page)
        yield self.get_binanace_data(1, 20, "USDT", "BUY", "VND", self.parse_first_page)
        yield self.get_binanace_data(1, 20, "USDT", "SELL", "VND", self.parse_first_page)

        # Lấy tỷ giá cơ sở
        yield self.get_VCB_data()
        price_sell = response.xpath('//*[@id="maket"]/section/section/table/tr[4]/td[3]/text()').get()
        price_buy = response.xpath('//*[@id="maket"]/section/section/table/tr[4]/td[4]/text()').get()

        yield {
            "exchange": "VTBank24",
            "tradeType": "SELL",
            "asset": "USD",
            "fiat": "RUB",
            "price": float(price_sell.replace(',','.')),
            "tradeMethods": ['BankTransferRussia'],
            "minSingleTransAmount": 0.0,
            "maxSingleTransAmount": 10000000000000.0,
            "monthFinishRate": 1.0,
            "monthOrderCount": 100000
        }
        yield {
            "exchange": "VTBank24",
            "tradeType": "BUY",
            "asset": "USD",
            "fiat": "RUB",
            "price": float(price_buy.replace(',','.')),
            "tradeMethods": ['BankTransferRussia'],
            "minSingleTransAmount": 0.0,
            "maxSingleTransAmount": 10000000000000.0,
            "monthFinishRate": 1.0,
            "monthOrderCount": 100000
        }

    
    def parse_vcb_page(self, response):
        stringData = response.text.split('\n', 2)[2]
        root = ET.fromstring(stringData)

        for child in root:
            data = child.attrib
            if data != {} and data['CurrencyCode'] == 'USD':
                yield {
                    "exchange": "VietcomBank",
                    "tradeType": "SELL",
                    "asset": "USD",
                    "fiat": "VND",
                    "price": float(data['Sell'].replace(',', '')),
                    "tradeMethods": [],
                    "minSingleTransAmount": 0.0,
                    "maxSingleTransAmount": 10000000000000.0,
                    "monthFinishRate": 1.0,
                    "monthOrderCount": 100000
                }
                yield {
                    "exchange": "VietcomBank",
                    "tradeType": "BUY",
                    "asset": "USD",
                    "fiat": "VND",
                    "price": float(data['Buy'].replace(',', '')),
                    "tradeMethods": [],
                    "minSingleTransAmount": 0.0,
                    "maxSingleTransAmount": 10000000000000.0,
                    "monthFinishRate": 1.0,
                    "monthOrderCount": 100000
                }
                break

    def parse_first_page(self, response):
        data = json.loads(response.text)
        total_pages = math.ceil(data["total"]/20)
        payload = response.meta
        # print(payload["tradeType"], ":  ", data["total"])
        for page in range(1, total_pages+1):
            yield self.get_binanace_data(page, payload["rows"], payload["asset"], payload["tradeType"], payload["fiat"], self.parse_all_page)

    def parse_all_page(self, response):
        data = json.loads(response.text)
        for offer in data["data"]:
            data = {
                "exchange": "binance",
                "tradeType": response.meta["tradeType"],
                "asset": response.meta["asset"],
                "fiat": response.meta["fiat"],
                "price": float(offer['adv']['price']),
                "tradeMethods": [method['identifier'] for method in offer['adv']['tradeMethods']],
                "minSingleTransAmount": float(offer['adv']['minSingleTransAmount']),
                "maxSingleTransAmount": float(offer['adv']['maxSingleTransAmount']),
                "monthFinishRate": float(offer['advertiser']['monthFinishRate']),
                "monthOrderCount": int(offer['advertiser']['monthOrderCount'])
            }
            yield data