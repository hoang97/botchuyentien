import logging, pytz, sys
from typing import Coroutine
from datetime import datetime
from inspect import cleandoc
from functools import wraps
from copy import deepcopy

from telegram import Update
from telegram._utils.logging import get_logger
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils import *
from typing import Any

TIMEZONE = pytz.timezone('Europe/Moscow')

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


def is_admin(func):
    """Decorator to check Admin"""

    @wraps(func)
    async def inner(update: Update, context: ContextTypes.DEFAULT_TYPE):
        config = context.bot_data
        user = update.message.from_user.username
        if (user in config.list_admin):
            return await func(update, context)
        else:
            await update.message.reply_text('Bạn phải là Admin mới có thể sử dụng chức năng này!')
    return inner

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends explanation on how to use the bot."""
    explanation = '''        
        /help - danh sách lệnh
        /schedule - <seconds> - lên lịch đăng bài channel public
        /stop - <channel> - hủy lịch đăng bài channel public hoặc ctv
        /rate - <profit percent> - xem tỷ giá cho khách hàng trực tiếp
        /config - xem các thông số cài đặt hiện tại
        /update_config - <key> <value> - cập nhật lại thông số cài đặt
        /admin - xem danh sách Admin 
        /add_admin - <username> - thêm mới 1 admin
        /remove_admin - <username> - xóa 1 admin cũ
        /login - <username> <api_key> <api_secret> - đăng nhập tài khoản Bybit
        /logout - <username> - đăng xuất tài khoản Bybit
        /account - danh sách các Bybit account đang hiện có
    '''
    await update.message.reply_text(cleandoc(explanation))


async def alarm(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the alarm message."""
    config = context.bot_data
    p2p = config.p2p
    profit = config.profit_percent
    rate = p2p.get_exchange_rate()
    vnd_min = config.vnd_min
    vnd_max = config.vnd_max
    rub_min = config.rub_min
    rub_max = config.rub_max
    market_vnd = config.market_vnd
    market_rub = config.market_rub
    current_rate = get_rate(profit, rate, vnd_min, vnd_max, rub_min, rub_max, market_vnd, market_rub)
    if current_rate:
        [vnd2rub_vnd, vnd2rub_rub, rub2vnd_vnd, rub2vnd_rub] = current_rate
        msg = f'''
🔥 Cập nhật tỷ giá {datetime.now(pytz.utc).astimezone(TIMEZONE).strftime("%d/%m/%Y, %H:%M")} Moscow 🔥

🔥  Tỷ giá Chuyển tiền Việt - Nga 🔥
    
        💰 VND-RUB: {round(vnd2rub_vnd/100)*100} / {round(vnd2rub_rub)} 😍

        💰 RUB-VND: {round(rub2vnd_rub)} / {round(rub2vnd_vnd/100)*100} 😍

👇 Để chuyển tiền vui lòng liên hệ 👇
        '''
        keyboard = [
            [
                InlineKeyboardButton("Telegram", url='https://t.me/annguyento'),
                InlineKeyboardButton("Facebook", url='https://www.facebook.com/chuyentienSPB')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(config.tele_channel, text=msg, reply_markup=reply_markup)
    else:
        await context.bot.send_message(config.tele_admin_group, text="Tỷ giá nằm ngoài range đã định")


def remove_job_if_exists(name: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True


def logout_account_if_exists(username: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.bot_data.bybit_queue
    if current_jobs:
        job = current_jobs.pop(username, None)
        if job:
            job['task'].cancel()
            job['account'].remove()
            return True
    return False


@is_admin
async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a job to the queue."""
    config = context.bot_data
    chat_id = update.effective_message.chat_id
    job_name = f"Schedule channel {config.tele_channel}"
    try:
        interval = int(context.args[0])
        if interval < 0:
            await update.message.reply_text("Không thể đặt số âm !!!")
            return

        remove_job_if_exists(job_name, context)
        context.job_queue.run_repeating(alarm, first=0, interval=interval, chat_id=chat_id, name=job_name)

        text = f"Lên lịch thành công, gửi thông báo lên channel sau mỗi {interval} giây"
        await update.message.reply_text(text)

    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /schedule <seconds>")


@is_admin
async def unset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove the job if the user changed their mind."""
    config = context.bot_data
    job_name = f"Schedule channel {config.tele_channel}"
    job_removed = remove_job_if_exists(job_name, context)
    text = "Đã dừng gửi thông báo lên channel" if job_removed else "Hiện không có lịch nào để hủy"
    await update.message.reply_text(text)


async def show_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current running config"""
    config = context.bot_data.obj
    text = 'Thông số cài đặt hiện tại:\n'
    for key in config.keys():
        if not key.startswith('_'):
            text += f'- {key}: {config[key]}\n'
    await update.message.reply_text(text)


@is_admin
async def update_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data
    try:
        key = context.args[0]
        value = int(context.args[1])
        error = ""
        if value < 0:
            error = f"{key} không thể âm"
        else:
            config_obj = deepcopy(config.obj)
            config_obj[key] = value
            if (config_obj['MARKET_VND'] > config_obj['VND_MAX']) or (config_obj['MARKET_VND'] < config_obj['VND_MIN']):
                error = f"MARKET_VND không nằm trong range {config_obj['VND_MIN']} - {config_obj['VND_MAX']}"
            if (config_obj['MARKET_RUB'] > config_obj['RUB_MAX']) or (config_obj['MARKET_RUB'] < config_obj['RUB_MIN']):
                error = f"MARKET_RUB không nằm trong range {config_obj['RUB_MIN']} - {config_obj['RUB_MAX']}"
            
        if error:
            await update.message.reply_text(f"Đổi cấu hình không thành công:\n- {error}")
        else:
            config.update(key, value)
            await update.message.reply_text(f"Đổi cấu hình thành công:\n- {key}: {value}")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /update_config <key> <value>")


async def show_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data
    text = f"Danh sách admin:\n"
    for admin in config.obj['_LIST_ADMIN']:
        text += f"- {admin}\n"
    await update.message.reply_text(text)


@is_admin
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data
    try:
        list_admin = config.obj['_LIST_ADMIN']
        user = context.args[0]
        if user in list_admin:
            await update.message.reply_text(f"User {user} đã là admin")
        else:
            list_admin.append(user)
            config.save()
            text = f"Thêm Admin {user} thành công\nDanh sách admin:\n"
            for admin in list_admin:
                text += f"- {admin}\n"
            await update.message.reply_text(text)
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /add_admin <username>")


@is_admin
async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = context.bot_data
    try:
        list_admin = config.obj['_LIST_ADMIN']
        user = context.args[0]
        if user in list_admin:
            list_admin.remove(user)
            config.save()
            text = f"Xóa Admin {user} thành công\nDanh sách admin:\n"
            for admin in list_admin:
                text += f"- {admin}\n"
            await update.message.reply_text(text)
        else:
            await update.message.reply_text(f"User {user} không phải là admin")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /remove_admin <username>")


async def current_rate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        profit = float(context.args[0])
        config = context.bot_data
        [rub, vnd, vnd2usdt, usdt2rub] = config.p2p.get_detail_rate()
        rate = add_profit(rub/vnd, profit)
        rub2vnd_vnd = config.market_vnd
        rub2vnd_rub = rub2vnd_vnd*rate
        vnd2rub_vnd = rub2vnd_vnd + 300
        vnd2rub_rub = rub2vnd_rub
        msg = f'''
🔥 Cập nhật tỷ giá {datetime.now(pytz.utc).astimezone(TIMEZONE).strftime("%d/%m/%Y, %H:%M")} Moscow 🔥

🔥  Tỷ giá Chuyển tiền Việt - Nga 🔥

        💰 VND-RUB: {round(vnd2rub_vnd/100)*100} / {round(vnd2rub_rub)} 😍

        💰 RUB-VND: {round(rub2vnd_rub)} / {round(rub2vnd_vnd/100)*100} 😍

🔥  Trung bình 100 giao dịch Bybit 🔥

        💰 RUB-USDT: {rub}

        💰 USDT-VND: {vnd}

🔥  Top giao dịch Bybit 🔥
'''
        for _, row in usdt2rub.iterrows():
            msg += f"\n       💰 RUB-USDT: {row['nickName']} {row['price']} {row['recentExecuteRate']}%\n"
        for _, row in vnd2usdt.iterrows():
            msg += f"\n       💰 USDT-VND: {row['nickName']} {row['price']} {row['recentExecuteRate']}%\n"
        await update.message.reply_text(msg)
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /rate <profit percent>")


async def list_bybit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    jobs = context.bot_data.bybit_queue
    accounts = jobs.keys()
    msg = f"Hiện có {len(accounts)} account đang chạy"
    for username in accounts:
        msg += f"\n- {username}"
    await update.message.reply_text(msg)


async def login_bybit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_message.chat_id
    current_jobs = context.bot_data.bybit_queue
    try:
        username = str(context.args[0])
        api_key = str(context.args[1])
        api_secret = str(context.args[2])
        account = BybitAccount(username, api_key, api_secret)

        resp = await account.authenticate()
        if resp["success"]:
            logout_account_if_exists(username, context)
            task = asyncio.create_task(account.subcribe_wallet_stream(context.bot, chat_id))
            current_jobs[username] = {
                'task': task,
                'account': account
            }
        else:
            await update.message.reply_text("Đăng nhập không thành công!!!")
            return

        account.save()
        text = f"Đăng nhập account {username} thành công"
        await update.message.reply_text(text)

    except Exception as e:
        if type(e) in (IndexError, ValueError):
            await update.message.reply_text("Usage: /login <username> <api_key> <api_secret>")
        else:
            await update.message.reply_text(f"Login has error: {e}")


async def logout_bybit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        username = str(context.args[0])
        logout_account_if_exists(username, context)
        await update.message.reply_text(f"Đăng xuất thành công account {username}")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /logout <username>")


def main() -> None:
    """Run bot."""
    # Create the Application and pass it your bot's token.
    config = Config()
    config.p2p = BybitP2P(config.bybit_cookie)
    config.bybit_queue = {}
    application = Application.builder().token(config.tele_token).build()
    application.bot_data = config

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler(["start", "help"], start))
    application.add_handler(CommandHandler("schedule", schedule))
    application.add_handler(CommandHandler("config", show_config))            # show config
    application.add_handler(CommandHandler("update_config", update_config))     # update config
    application.add_handler(CommandHandler("admin", show_admin))
    application.add_handler(CommandHandler("add_admin", add_admin))
    application.add_handler(CommandHandler("remove_admin", remove_admin))
    application.add_handler(CommandHandler("rate", current_rate))              # get exchange rate with profit
    application.add_handler(CommandHandler("account", list_bybit))
    application.add_handler(CommandHandler("login", login_bybit))
    application.add_handler(CommandHandler("logout", logout_bybit))
    application.add_handler(CommandHandler("stop", unset))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()