import logging
import subprocess
import pytz
import sqlite3
from os import name

from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from telegram.ext.dispatcher import Dispatcher

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)
PRIVATE_ID = '1395019328'
DEVELOPER_ID = '-1001786996731'
DEVELOPER_TIMEZONE = pytz.timezone('Europe/Moscow')

# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.
# Best practice would be to replace context with an underscore,
# since context is an unused local variable.
# This being an example and not having context present confusing beginners,
# we decided to have it present as context.
def start(update: Update, context: CallbackContext) -> None:
    """Sends explanation on how to use the bot."""
    update.message.reply_text('''
        Xin chào!
/help - danh sách lệnh
/publish - <seconds> <channel> - lên lịch đăng bài channel public hoặc ctv
/stop - <channel> - hủy lịch đăng bài channel public hoặc ctv
/list - xem danh sách lịch đăng bài
/current_rate - xem tỷ giá chi tiết
/set_profit - <vnd2rub_profit> <rub2vnd_profit> - thay đổi tỷ lệ lợi nhuận
    ''')


def get_info(context: CallbackContext) -> None:
    """
    Run subprocess to scrapy
    """
    job = context.job
    to_dev = job.context.get('to_dev', '')
    to_public = job.context.get('to_public', '')
    to_ctv = job.context.get('to_ctv', '')
    
    # context.bot.send_message(job.context, text='Bắt đầu lấy dữ liệu!')
    subprocess.run(['scrapy','crawl','autoBinanceRate','-a',f'to_dev={to_dev}','-a',f'to_public={to_public}','-a',f'to_ctv={to_ctv}'])
    # context.bot.send_message(job.context, text='Đã lấy dữ liệu xong!')


def remove_job_if_exists(name: str, context: CallbackContext) -> bool:
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True


def set_timer(update: Update, context: CallbackContext) -> None:
    """Add a job to the queue."""
    chat_id = update.message.chat.id
    try:
        # args[0] should contain the time for the timer in seconds
        interval = int(context.args[0])
        channel = context.args[1]
        if interval < 2:
            update.message.reply_text('Xin lỗi mỗi lần lấy dữ liệu phải cách nhau ít nhất 2s!')
            return

        if channel not in ['public', 'ctv']:
            raise ValueError
        
        job_name = channel
        job_context = {
            'to_dev': 'n',
            'to_public': 'y' if channel == 'public' else 'n',
            'to_ctv': 'y' if channel == 'ctv' else 'n'
        }

        job_removed = remove_job_if_exists(job_name, context)
        context.job_queue.run_repeating(get_info, interval=interval, first=2, context=job_context, name=job_name)

        text = f'Lên lịch đăng bài channel {channel} thành công!'
        if job_removed:
            text += ' Lịch cũ đã bị hủy.'
        text += f'\nĐăng bài vào channel {channel} mỗi {interval}s'
        text += '\nBắt đầu thực thi sau 2s ...'
        update.message.reply_text(text)

    except (IndexError, ValueError):
        update.message.reply_text('Usage: /set <seconds> <channel> (channel = {public, ctv})')

def unset(update: Update, context: CallbackContext) -> None:
    """Remove the job if the user changed their mind."""
    chat_id = update.message.chat_id
    try:
        channel = context.args[0]
        if channel not in ['public', 'ctv']:
            raise ValueError
        job_name = channel
        job_removed = remove_job_if_exists(job_name, context)
        text = f'Đã hủy lịch đăng bài channel {channel} thành công!' if job_removed else f'Hiện không có lịch đăng bài channel {channel} nào.'
        update.message.reply_text(text)

    except (IndexError, ValueError):
        update.message.reply_text('Usage: /unset <channel> (channel = {public, ctv})')

def list_job(update: Update, context: CallbackContext) -> None:
    """List time run of all current jobs"""
    jobs = list(context.job_queue.jobs())
    msg = f'Hiện có {len(jobs)} lịch đang chạy'
    for job in jobs:
        msg += f'\n{job.name} sẽ chạy lúc {job.next_t.astimezone(DEVELOPER_TIMEZONE).strftime("%d %b %Y, %H:%M:%S")}'
    update.message.reply_text(msg)

def get_rate(update: Update, context: CallbackContext )-> None:
    """Get detail rate for dev"""
    chat_id = update.message.chat_id
    try:
        # username = context.args[0]
        job_name = "GetInfo_" + str(chat_id)
        job_removed = remove_job_if_exists(job_name, context)
        job_context = {
            'to_dev': 'y',
            'to_public': 'n',
            'to_ctv': 'n'
        }
        context.job_queue.run_once(get_info, when=2, context=job_context, name=job_name)

        text = ''
        if job_removed:
            text += 'Job cũ đã bị hủy.'
        text += '\nBắt đầu lấy dữ liệu sau 2s ...'
        update.message.reply_text(text)
    except (IndexError, ValueError):
        update.message.reply_text('Usage: /current_rate')

def set_profit(update: Update, context: CallbackContext )-> None:
    """Set the profit for exchange"""
    try:
        vnd2rub_profit = context.args[0]
        rub2vnd_profit = context.args[1]
        # Connect to database
        connection = sqlite3.connect("db/data.db")
        cursor = connection.cursor()

        # Try to create table
        cursor.execute( '''
            CREATE TABLE IF NOT EXISTS vars(
                name TEXT UNIQUE,
                value INTEGER
            )
        ''' )

        # Try to update or insert variable
        cursor.execute('''
            INSERT OR REPLACE INTO vars (name, value)
            VALUES  ('vnd2rub_profit', ?)
        ''', vnd2rub_profit)

        cursor.execute('''
            INSERT OR REPLACE INTO vars (name, value)
            VALUES  ('rub2vnd_profit', ?)
        ''', rub2vnd_profit)

        connection.commit()
        connection.close()
        logging.info('Disconnected from database!')
        update.message.reply_text(f'🎉 Thay đổi tỷ lệ lợi nhuận thành công!!! 🎉\n\nTỷ lệ lợi nhuận hiện tại là: \n\n     VND-RUB: {vnd2rub_profit}%\n     RUB-VND: {rub2vnd_profit}%')

    except (IndexError, ValueError):
        update.message.reply_text('Usage: /set_profit <vnd2rub_profit> <rub2vnd_profit>')

def auto_start_crawl(updater:Updater, dispatcher:Dispatcher):
    msg = '''
Server đã khởi động lại
Tự động lên lịch đăng bài channel public sau mỗi 3600s
Tự động lên lịch đăng bài channel ctv sau mỗi 300s
Bắt đầu thực thi sau 2s ...
    '''
    updater.bot.send_message(chat_id=PRIVATE_ID, text=msg)


    interval = 3600
    job_name = "public"
    job_context = {
        'to_dev': 'n',
        'to_public': 'y',
        'to_ctv': 'n'
    }
    dispatcher.job_queue.run_repeating(get_info, interval=interval, first=2, context=job_context, name=job_name)

    interval = 300
    job_name = "ctv"
    job_context = {
        'to_dev': 'n',
        'to_public': 'n',
        'to_ctv': 'y'
    }
    dispatcher.job_queue.run_repeating(get_info, interval=interval, first=2, context=job_context, name=job_name)


def main() -> None:
    """Run bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater("5225045930:AAHo07BayUikgm2JHyS17ArY0iryUlkR7wI")

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", start))
    dispatcher.add_handler(CommandHandler("publish", set_timer))
    dispatcher.add_handler(CommandHandler("stop", unset))
    dispatcher.add_handler(CommandHandler("list", list_job))
    dispatcher.add_handler(CommandHandler("current_rate", get_rate))
    dispatcher.add_handler(CommandHandler("set_profit", set_profit))

    # Start the Bot
    updater.start_polling()
    
    auto_start_crawl(updater, dispatcher)
    # Block until you press Ctrl-C or the process receives SIGINT, SIGTERM or
    # SIGABRT. This should be used most of the time, since start_polling() is
    # non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()