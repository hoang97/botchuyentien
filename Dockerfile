FROM python:3.8-slim-buster

WORKDIR /home/app

RUN pip install --upgrade pip
COPY ./requirements.txt /home/app/requirements.txt
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "telegram_bot.py"]