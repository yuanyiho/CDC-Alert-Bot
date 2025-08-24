import sys
import time
import json
import httpx
import random
import logging
import datetime
import configparser
import undetected_chromedriver as uc
from pathlib import Path
from distutils.util import strtobool
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

class CDCAlertBotClass:
    def __init__(self):
        self.config_file = Path("./config/config.cfg")
        self.config_parser = configparser.ConfigParser()
        self.config_parser.read(self.config_file)
        
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", 
            handlers=[
                logging.FileHandler(Path("./logs/logging.txt")),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger("CDC Alert Bot")
        
        # Retrieve Telegram Configuration
        self.is_telegram_enabled = strtobool(self.config_parser.get("telegram_config", "is_telegram_enabled"))
        if self.is_telegram_enabled:
            self.logger.info("Telegram Alert is enabled")
            self.telegram_bot_key = self.config_parser.get("telegram_config", "telegram_bot_key")
            self.telegram_chat_id = self.config_parser.get("telegram_config", "telegram_chat_id")
            
            self.use_telegram_chat_thread = strtobool(self.config_parser.get("telegram_config", "use_telegram_chat_thread"))
            if self.use_telegram_chat_thread:
                self.logger.info("Alert via Telegram Chat Thread is enabled")
                self.telegram_chat_thread_id = self.config_parser.get("telegram_config", "telegram_chat_thread_id")
            else:
                self.logger.info("Alert via Telegram Chat Thread not enabled")
            
        else:
            self.logger.info("Telegram Alert is not enabled")
        
        # Retrieve 2Captcha Configuration
        self.captcha_key = self.config_parser.get("2captca_config", "captcha_key")
        self.captcha_polling_retry_seconds = int(self.config_parser.get("2captca_config", "captcha_polling_retry_seconds"))
        self.captcha_max_attempts = int(self.config_parser.get("2captca_config", "captcha_max_attempts"))
        
        # Retrieve CDC Configuration
        self.cdc_user = self.config_parser.get("cdc_config", "cdc_user")
        self.cdc_pass = self.config_parser.get("cdc_config", "cdc_pass")
        self.cdc_url = self.config_parser.get("cdc_config", "cdc_url")
        self.cdc_team = self.config_parser.get("cdc_config", "cdc_team").strip('"')

    # Send notification of available slots via telegram message
    def send_telegram_message(self, message):
        if self.is_telegram_enabled:
            url = f"https://api.telegram.org/bot{self.telegram_bot_key}/sendMessage"
            
            if self.use_telegram_chat_thread:
                payload = {
                    "chat_id": self.telegram_chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                    "message_thread_id": self.telegram_chat_thread_id
                }
            else:
                payload = {
                    "chat_id": self.telegram_chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }

            try:
                with httpx.Client(timeout=10) as client:
                    resp = client.post(url, data=payload)
                    if resp.status_code == 200:
                        self.logger.info("Telegram message sent.")
                    else:
                        self.logger.error(f"Telegram failed: {resp.text}")
            except Exception as e:
                self.logger.error(f"Telegram error: {e}")

    # Solve the captcha
    def solve_recaptcha(self, driver, page_url):
        """Solves reCAPTCHA v2 via 2Captcha and injects token only (no click or extra callback)."""

        # Locate the sitekey
        try:
            sitekey_elem = driver.find_element(By.CSS_SELECTOR, "[data-sitekey]")
            sitekey = sitekey_elem.get_attribute("data-sitekey")
            self.logger.info("reCAPTCHA sitekey found")
        except Exception:
            self.logger.error("No reCAPTCHA sitekey found")
            return False, "NO_RECAPTCHA_V2_FOUND"

        self.logger.info(f"[2Captcha] Sending solve request (sitekey={sitekey[:8]}…)")

        # Request solve
        with httpx.Client(timeout=30) as client:
            task_id = client.post("http://2captcha.com/in.php", data={
                "key": self.captcha_key,
                "method": "userrecaptcha",
                "googlekey": sitekey,
                "pageurl": page_url,
                "json": 1,
            }).json()["request"]

            token = None
            for i in range(self.captcha_max_attempts):
                time.sleep(self.captcha_polling_retry_seconds)
                res = client.get("http://2captcha.com/res.php", params={
                    "key": self.captcha_key,
                    "action": "get",
                    "id": task_id,
                    "json": 1
                }).json()
                if res["status"] == 1:
                    token = res["request"]
                    break
                self.logger.info(f"[2Captcha] Waiting… ({i+1}/{self.captcha_max_attempts})")

            if not token:
                return False, "2CAPTCHA_SOLVE_FAILED"

        self.logger.info("[2Captcha] Token received, injecting…")

        # Inject token into g-recaptcha-response using .innerText
        try:
            driver.execute_script(
                """document.querySelector('[name="g-recaptcha-response"]').innerText = arguments[0];""",
                token
            )
            return True, "SUCCESS"
        except Exception as e:
            self.logger.info(f"Token injection failed: {e}")
            return False, "INJECTION_FAILED"

    def check_practical_slot(self, driver):
        booking_url = "https://bookingportal.cdc.com.sg/NewPortal/Booking/BookingPL.aspx"
        driver.get(booking_url)

        try:
            # Wait for the dropdown to appear
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.ID, "ctl00_ContentPlaceHolder1_ddlCourse"))
            )
            self.logger.info("[CDC] Course dropdown loaded.")

            # Select the team
            course_dropdown = Select(driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_ddlCourse"))
            course_dropdown.select_by_value(self.cdc_team)
            self.logger.info(f"[CDC] Course selected: {self.cdc_team}")

            # ✅ Wait up to 5s for full booking message (if any) to appear
            time.sleep(3)

            # Check for "Fully Booked" message
            full_msg_exists = len(driver.find_elements(By.ID, "ctl00_ContentPlaceHolder1_lblFullBookMsg")) > 0
            if full_msg_exists:
                self.logger.info("[CDC] No slots available — fully booked.")
                return False
            else:
                self.logger.info("[CDC] Slots available! - Checking for the month availability")
                self.send_telegram_message("Slots available! - Checking for the month availability")

                # Wait until any of the session texts contain "available"
                wait = WebDriverWait(driver, 30)
                available_found = wait.until(lambda d: any(
                    "available" in (d.find_element(By.ID, f"ctl00_ContentPlaceHolder1_lblM{i}SesNo").text.lower() or "")
                    for i in range(1, 4)
                    if len(d.find_elements(By.ID, f"ctl00_ContentPlaceHolder1_lblM{i}SesNo")) > 0
                ))

                # Mapping of M1/M2/M3 to their label and month
                session_months = {}
                now = datetime.datetime.now()
                for i in range(1, 4):
                    label_id = f"ctl00_ContentPlaceHolder1_lblM{i}SesNo"
                    if len(driver.find_elements(By.ID, label_id)) == 0:
                        continue

                    text = driver.find_element(By.ID, label_id).text
                    session_month = (now.month + (i - 1) - 1) % 12 + 1
                    session_months[f"M{i}"] = {
                        "label_id": label_id,
                        "text": text,
                        "month": datetime.datetime(now.year + ((now.month + (i - 1) - 1) // 12), session_month, 1).strftime("%b")
                    }

                for key, info in session_months.items():
                    if "available" in info["text"].lower():
                        msg = f"Slots available in {info['month']} ({key}) — {info['text']}"
                        self.logger.info(msg)
                        self.send_telegram_message(msg)

                return True

        except Exception as e:
            self.logger.error(f"Error checking slot availability: {e}")
            self.send_telegram_message(f"Bot faced issue in checking slot availability - {e}")
            return False

    # Check for available slots and alert if enabled
    def check_for_slot_and_alert(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--no-proxy-server")
        executable_path = Path("./drivers/windows/chromedriver.exe")
        service = ChromeService(executable_path)
        driver = uc.Chrome(options=options)

        try:
            # Enable and adjust line 222 if you are using multiple monitor
            #driver.set_window_position(-2000, 0)
            driver.set_window_size(1600, 768)

            self.logger.info(f"[CDC] Navigating to CDC Website - {self.cdc_url}")
            driver.get(self.cdc_url)
            time.sleep(10)
            self.logger.info(f"[CDC] Waiting for login modal to show up")
            
            wait = WebDriverWait(driver, 30)
            # Username Input
            user_input = wait.until(EC.presence_of_element_located((By.NAME, "userId_4")))
            user_input.send_keys(self.cdc_user)

            # Password Input
            pass_input = wait.until(EC.presence_of_element_located((By.NAME, "password_4")))
            pass_input.send_keys(self.cdc_pass)

            # Solve reCAPTCHA
            result, captcha_msg = self.solve_recaptcha(driver, self.cdc_url)
            if not result:
                self.logger.error(f"Captcha failed - {captcha_msg}")
                self.logger.info(f"Exiting program due to unable to login")
                driver.quit()
                sys.exit()
            else:
                self.logger.info("[CDC] Captcha solved - Logging in")
            
            # Proceed to login
            driver.find_element(By.CSS_SELECTOR, ".btn-login-submit").click()
            time.sleep(5)
            
            self.logger.info("[CDC] Checking for available practical slots")
            result = self.check_practical_slot(driver)
        
        finally:
            driver.quit()
    
    def run(self):
        try:
            while True:
                self.logger.info("\nNew cycle starting…")
                self.check_for_slot_and_alert()
                delay = random.randint(15*60, 20*60)
                next_run = datetime.datetime.now() + datetime.timedelta(seconds=delay)
                self.logger.info(f"Sleeping for {delay//60} min {delay%60:02d} s…")
                self.logger.info(f"Next cycle at: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
                self.logger.info(f"Press CTRL C to stop anytime")
                time.sleep(delay)
        except KeyboardInterrupt:
            self.logger.info("Script has been stopped.")