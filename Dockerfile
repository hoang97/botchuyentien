FROM python:3.11.10-slim-bullseye

WORKDIR /home/app

RUN pip install --upgrade pip
COPY ./requirements.txt /home/app/requirements.txt
RUN pip install -r requirements.txt

COPY ./src/* /home/app

CMD ["python", "telegram_bot.py"]