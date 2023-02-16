# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
import logging, sqlite3
import pandas as pd
import pytz
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

DEVELOPER_ID = '-1001786996731'
PUBLIC_ID = '@chuyentienspb'
CTV_ID = '-1001503353838'
TIMEZONE = pytz.timezone('Europe/Moscow')

class AutoexchangeratePipeline:
    data = []
    prices = {}

    def open_spider(self, spider):
        # Connect to database
        self.connection = sqlite3.connect("db/data.db")
        self.cursor = self.connection.cursor()

        # Try to create table
        self.cursor.execute( '''
            CREATE TABLE IF NOT EXISTS vars(
                name TEXT UNIQUE,
                value INTEGER
            )
        ''' )

        # Try to insert profit vnd-rub variable
        self.cursor.execute('''
            SELECT value FROM vars WHERE name='vnd2rub_profit'
        ''')
        entry = self.cursor.fetchone()

        if entry is None:
            self.cursor.execute('''
                INSERT INTO vars (name, value)
                VALUES ('vnd2rub_profit', 2)
            ''')
            self.vnd2rub_profit = 2
        else :
            self.vnd2rub_profit = entry[0]

        # Try to insert profit rub-vnd variable
        self.cursor.execute('''
            SELECT value FROM vars WHERE name='rub2vnd_profit'
        ''')
        entry = self.cursor.fetchone()

        if entry is None:
            self.cursor.execute('''
                INSERT INTO vars (name, value)
                VALUES ('rub2vnd_profit', 2)
            ''')
            self.rub2vnd_profit = 2
        else :
            self.rub2vnd_profit = entry[0]

        self.connection.commit()
        logging.info('Connected to database!')

    def process_item(self, item, spider):
        # print(item)
        self.data.append(item)

    def close_spider(self, spider):
        dataframe = pd.DataFrame(self.data)

        grouped_dataframe = dataframe.groupby(['exchange', 'tradeType', 'asset', 'fiat'])
        # print(grouped_dataframe.groups)
        for key in grouped_dataframe.groups:
            ind = grouped_dataframe.groups[key]
            data = dataframe.loc[ind]
            month_order_count = data['monthOrderCount'].quantile(0.5)
            data = data[(data['monthOrderCount'] >= month_order_count) & (data['monthFinishRate'] >= 0.9)]

            self.prices[key] = {
                "Min Price": data['price'].min(),
                "25% Price": data['price'].quantile(0.25),
                "50% Price": data['price'].quantile(0.5),
                "75% Price": data['price'].quantile(0.75),
                "Max Price": data['price'].max(),
                "Price": data['price'].nsmallest(30).max() if key[1] == 'BUY' else data['price'].nlargest(30).min()
            }

        # Định nghĩa
        # base_SELL_USD_RUB = self.prices[('VTBank24', 'SELL', 'USD', 'RUB')]['75% Price']
        # base_BUY_USD_RUB = self.prices[('VTBank24', 'BUY', 'USD', 'RUB')]['25% Price']
        # base_SELL_USD_VND = self.prices[('VietcomBank', 'BUY', 'USD', 'VND')]['75% Price']
        # base_BUY_USD_VND = self.prices[('VietcomBank', 'SELL', 'USD', 'VND')]['25% Price']
        # binance_SELL_USDT_RUB = self.prices[('binance', 'SELL', 'USDT', 'RUB')]['75% Price']
        # binance_BUY_USDT_RUB = self.prices[('binance', 'BUY', 'USDT', 'RUB')]['25% Price']
        # binance_SELL_USDT_VND = self.prices[('binance', 'SELL', 'USDT', 'VND')]['75% Price']
        # binance_BUY_USDT_VND = self.prices[('binance', 'BUY', 'USDT', 'VND')]['25% Price']

        base_SELL_USD_RUB = self.prices[('VTBank24', 'SELL', 'USD', 'RUB')]['Price']
        base_BUY_USD_RUB = self.prices[('VTBank24', 'BUY', 'USD', 'RUB')]['Price']
        base_SELL_USD_VND = self.prices[('VietcomBank', 'BUY', 'USD', 'VND')]['Price']
        base_BUY_USD_VND = self.prices[('VietcomBank', 'SELL', 'USD', 'VND')]['Price']
        binance_SELL_USDT_RUB = self.prices[('binance', 'SELL', 'USDT', 'RUB')]['Price']
        binance_BUY_USDT_RUB = self.prices[('binance', 'BUY', 'USDT', 'RUB')]['Price']
        binance_SELL_USDT_VND = self.prices[('binance', 'SELL', 'USDT', 'VND')]['Price']
        binance_BUY_USDT_VND = self.prices[('binance', 'BUY', 'USDT', 'VND')]['Price']

        # Giá giao dịch
        vnd2rub_vnd = base_BUY_USD_VND + 250
        vnd2rub_rub = vnd2rub_vnd/binance_BUY_USDT_VND*binance_SELL_USDT_RUB*(1-self.vnd2rub_profit/100)

        rub2vnd_vnd = base_SELL_USD_VND
        rub2vnd_rub = rub2vnd_vnd*binance_BUY_USDT_RUB/binance_SELL_USDT_VND/(1-self.rub2vnd_profit/100)

        if spider.to_dev == 'y':
            self.send_message_to_dev(spider, vnd2rub_vnd, vnd2rub_rub, rub2vnd_vnd, rub2vnd_rub)
        if spider.to_public == 'y':
            self.send_message_to_public_channel(spider, vnd2rub_vnd, vnd2rub_rub, rub2vnd_vnd, rub2vnd_rub)
        if spider.to_ctv == 'y':
            self.send_message_to_ctv_channel(spider, vnd2rub_vnd, vnd2rub_rub, rub2vnd_vnd, rub2vnd_rub)

        logging.info('Scraped successfully!!!')
        # Disconnect from database
        self.connection.close()
        logging.info('Disconnected from database!')

    def send_message_to_dev(self, spider, vnd2rub_vnd, vnd2rub_rub, rub2vnd_vnd, rub2vnd_rub):
        msg = ''
        for key in self.prices.keys():
            
            price = self.prices[key]
            if key[2] == 'USD':
                msg += f'\n📉 Tỷ giá {key[0]}: {key[1]} {key[2]} {key[3]} 💰 Giá: {price["Min Price"]}\n'
            else:
                msg += f'\n📉 Tỷ giá {key[0]}: {key[1]} {key[2]} {key[3]}\n'
                msg += f'\n     💰 Giá thấp nhất: {price["Min Price"]}'
                msg += f'\n     💰 Giá 25%      : {price["25% Price"]}'
                msg += f'\n     💰 Giá 50%      : {price["50% Price"]}'
                msg += f'\n     💰 Giá 75%      : {price["75% Price"]}'
                msg += f'\n     💰 Giá cao nhất : {price["Max Price"]}'
                msg += f'\n     💰 Giá hợp lí   : {price["Price"]}\n'
        msg += f'\n📉 Tỷ giá báo khách: \n'
        msg += f'\n     💵 VND-RUB: {round(vnd2rub_vnd/100)*100} / {round(vnd2rub_rub, 2)} 😍 (lãi {self.vnd2rub_profit}%)\n'
        msg += f'\n     💵 RUB-VND: {round(rub2vnd_rub, 2)} / {round(rub2vnd_vnd/100)*100} 😍 (lãi {self.rub2vnd_profit}%)\n'

        spider.bot.send_message(chat_id=DEVELOPER_ID, text=msg)

    def send_message_to_public_channel(self, spider, vnd2rub_vnd, vnd2rub_rub, rub2vnd_vnd, rub2vnd_rub):
        keys = [
            ('VTBank24', 'BUY', 'USD', 'RUB'),
            ('VTBank24', 'SELL', 'USD', 'RUB'),
            ('VietcomBank', 'BUY', 'USD', 'VND'),
            ('VietcomBank', 'SELL', 'USD', 'VND'),
        ]
        msg = f'''  
🔥 Cập nhật tỷ giá {datetime.now(pytz.utc).astimezone(TIMEZONE).strftime("%d %m %Y, %H:%M:%S")} Moscow 🔥
        '''

        for key in keys:
            price = self.prices[key]
            msg += f'\n📉 Tỷ giá {key[0]}: {key[1]} {key[2]} {key[3]} 💰 Giá: {price["Min Price"]}\n'

        msg += f'''
🔥  Tỷ giá Chuyển tiền Việt - Nga 🔥
    
    💰 VND-RUB: {round(vnd2rub_vnd/100)*100} / {int(vnd2rub_rub/10)}x 😍

    💰 RUB-VND: {int(rub2vnd_rub/10)}x / {round(rub2vnd_vnd/100)*100} 😍

👇 Để có tỷ giá chính xác vui lòng liên hệ 👇
        '''
        keyboard = [
            [
                InlineKeyboardButton("Telegram", url='https://t.me/vuahn286'),
                InlineKeyboardButton("Facebook", url='https://www.facebook.com/chuyentienSPB')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        spider.bot.send_message(chat_id=PUBLIC_ID, text=msg, reply_markup=reply_markup)

    
    def send_message_to_ctv_channel(self, spider, vnd2rub_vnd, vnd2rub_rub, rub2vnd_vnd, rub2vnd_rub):
        msg = f'''
🔥 Cập nhật tỷ giá {datetime.now(pytz.utc).astimezone(TIMEZONE).strftime("%d %m %Y, %H:%M:%S")} Moscow 🔥

💰 VND-RUB: {round(vnd2rub_vnd/100)*100} / {round(vnd2rub_rub, 2)} 😍

💰 RUB-VND: {round(rub2vnd_rub, 2)} / {round(rub2vnd_vnd/100)*100} 😍
        '''
        keyboard = [
            [
                InlineKeyboardButton("Telegram", url='https://t.me/vuahn286'),
                InlineKeyboardButton("Facebook", url='https://www.facebook.com/chuyentienSPB')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        spider.bot.send_message(chat_id=CTV_ID, text=msg, reply_markup=reply_markup)