# ⚠️ DISCLAIMER: USE AT YOUR OWN RISK! ⚠️
You are potentially might be flagged for possible botting behaviour using this script. I cannot confirm what will happen but so far it is okay for me as it is still within acceptable range of running.

Feel free to fork the project and add more features! For e.g
1) Ability to book specific sessions when available
2) Reserving slots

# CDC Alert Bot

This is a very simple alert bot that scrape ComfortDelGro Driving Centre to help check available slots.
I have initially written this to automate and make it easy for my wife to book her lessons under ONETEAM-C3A.

It is not tested with other type of team.

You will need make adjustment and point to the correct drivers if you are using linux/osx.

---

## Credit
This script was inspired, simplified and recreated from referencing [Zhannyhong - CDC Bot](https://github.com/Zhannyhong/cdc-bot)

---

## Features

- Periodically check CDC for available timing
- Send available slots of the month to Telegram

---

## Folder Structure

```
CDC-Alert-Bot
├─ config/
│ └─ config.cfg
├─ drivers/
│ └─ linux
│   └─ chromedriver
│ └─ osx
│   └─ chromedriver
│ └─ windows
│   └─ chromedriver.exe
├─ logs/
│ └─ logging.txt
├─ src/
│ └─ CDCAlertBotClass.py
├─ main.py
├─ Pipfile
└─ requirements.txt
```

---

## Prerequisite
```
Python3.10
2Captcha
```
---

## 2CAPTCHA
```
This project uses a third party API that is unfortunately a paid service.

As of writing, the rates of using this API are relatively cheap (SGD$5 can last you for about a month of the program runtime). To continue using this project, head over to 2captcha.com

Create an account

Top up your account with sufficient credits

Copy your API Token and paste it into config.cfg
```
---

## Clone the project
```
git clone [https://github.com/yuanyiho/CDC-Alert-Bot.git](https://github.com/yuanyiho/CDC-Alert-Bot.git)

cd CDC-Alert-Bot
```

---

## Add in the necessary config
```
Modify config.cfg under ./config/ to allow the bot to work
```

## Using pipenv (recommended)
```
pipenv install -r requirements.txt
pipenv run python main.py
```

## venv + pip (Alternative if not using pipenv)
```
python3.10 -m venv venv
source venv/bin/activate   # On Linux/MacOS
# venv\Scripts\activate    # On Windows
pip install -r requirements.txt
python main.py
```
