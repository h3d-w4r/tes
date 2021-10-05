import time
import re
import sys
import getopt
import logging

from selenium import webdriver
from selenium.webdriver.android.webdriver import WebDriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.functions.messages import GetBotCallbackAnswerRequest

VISIT_COMMAND = '/visit'

"""
There are a few other bots, which you can find on this site https://dogeclick.com/
but they share the same Adv database, so you can choose one of them. Depends on a coin you
want to "mine"
"""
BOT_NAME = '@Dogecoin_click_bot'

CHROME_DRIVER_PATH = "./chromedriver"
GLOBAL_WAIT_IN_SECONDS = 5
CAPTCHA_XPATH = "//*[contains(text(), 'solve the reCAPTCHA to continue')]"

GNU_OPTIONS = ["sessions=", "port=", "dev"]
UNIX_OPTIONS = "s:p:d"

API_ID = 1096441
API_HASH = 'fa5a67d7e150c639d876724ec406868d'


class WebDriverManager:
    def __init__(self, driver_path: str, global_wait_in_sec: int, options: Options, dev_mode: bool, selenium_port: int):
        self.driver_path = driver_path
        self.global_wait_in_sec = global_wait_in_sec
        self.options = options
        self.dev_mode = dev_mode
        self.port = selenium_port
        self.wd = None

    def get_web_driver(self) -> WebDriver:
        if not self.wd:
            if not self.dev_mode:
                caps = {'browserName': 'chrome'}
                self.wd = webdriver.Remote(
                    command_executor=f'http://localhost:{self.port}/wd/hub',
                    desired_capabilities=caps,
                    options=self.options
                )
            else:
                self.wd = webdriver.Chrome(self.driver_path, chrome_options=self.options)

            if len(self.wd.window_handles) >= 2:
                self.wd.switch_to.window(self.wd.window_handles[0])

            self.wd.implicitly_wait(GLOBAL_WAIT_IN_SECONDS)

        return self.wd

    def close_web_driver(self):
        if self.wd:
            self.wd.quit()
            self.wd = None


def close_alert(wd: WebDriver):
    try:
        WebDriverWait(wd, 4).until(EC.alert_is_present())

        alert = wd.switch_to.alert
        alert.dismiss()
    except TimeoutException:
        pass
        # ignore
    except Exception as e:
        logging.info(f"Something went wrong: {e}")


def is_element_exists(wd: WebDriver, xpath: str) -> bool:
    return len(wd.find_elements_by_xpath(xpath)) != 0


def console_arguments(unix_options: str, gnu_options: list) -> (list, bool, int):
    arguments, non_arguments = getopt.getopt(sys.argv[1:], unix_options, gnu_options)

    if not arguments:
        print("Session (-s / --sessions) argument is required")
        sys.exit(2)

    session_list, is_dev, remote_port = ["anon"], False, 4444

    for arg, val in arguments:
        if arg in ("-s", "--sessions"):
            session_list = re.split(r"\s*,\s*", val)
        elif arg in ("-d", "--dev"):
            is_dev = True
        elif arg in ("-p", "--port"):
            remote_port = int(val)

    return session_list, is_dev, remote_port


async def get_chat_history(tc: TelegramClient, entity):
    return await tc(GetHistoryRequest(
        peer=entity,
        limit=1,
        max_id=0,
        min_id=0,
        offset_id=0,
        add_offset=0,
        offset_date=None,
        hash=0
    ))


async def handle(message, bot_entity, url_set: set, web_driver_manager: WebDriverManager) -> int:
    if re.search(r".*Press.*button to earn.*", message.message):
        url = message.reply_markup.rows[0].buttons[0].url
        button_data = message.reply_markup.rows[1].buttons[1].data
        message_id = message.id

        logging.info(f"New reward has been found: {url}")

        if url in url_set:
            await client.send_message(entity=bot_entity, message=VISIT_COMMAND)
            logging.info("Url: {} is already present in set".format(url))
            time.sleep(2)

        wd = web_driver_manager.get_web_driver()
        wd.get(url)
        time.sleep(3)

        close_alert(wd)

        if is_element_exists(wd, xpath=CAPTCHA_XPATH):
            logging.info(f"There was a captcha for url {url}")
            await client(GetBotCallbackAnswerRequest(
                bot_entity,
                message_id,
                data=button_data
            ))

        return 1

    elif re.search(r".*stay on the site.*", message.message):
        time_to_wait = int(re.sub(r'\D', '', message.message))
        logging.info(f"Staying on a site for {time_to_wait} seconds")
        time.sleep(time_to_wait + 2)

        return 1

    elif re.search(r".*there are no new ads available.*", message.message):
        logging.info("Sorry case, new /visit messages will be sent")
        await client.send_message(entity=bot_entity, message=VISIT_COMMAND)
        return 0

    elif re.search(r"You earned.*for visiting a site", message.message):
        logging.info("Your earned message was handled")
        return 1
    else:
        logging.info(f"Unknown message: {message}")
        return -1


async def safe_handle(message, bot_entity, url_set: set, web_driver_manager: WebDriverManager) -> int:
    try:
        return await handle(message, bot_entity, url_set, web_driver_manager)
    except Exception as e:
        logging.info(f"Something went wrong: {e}")
        web_driver_manager.close_web_driver()
        return -1


async def run(dev_mode: bool, selenium_port: int):
    bot_entity = await client.get_entity(BOT_NAME)

    options = Options()
    options.add_extension("extension_4_0_8_8.crx")
    options.add_extension("extension_4_10_0_0.crx")

    web_driver_manager: WebDriverManager = WebDriverManager(
        selenium_port=selenium_port,
        dev_mode=dev_mode,
        driver_path=CHROME_DRIVER_PATH,
        global_wait_in_sec=GLOBAL_WAIT_IN_SECONDS,
        options=options
    )

    url_set: set = set()
    await client.send_message(entity=bot_entity, message=VISIT_COMMAND)
    time.sleep(5)

    sorry_message_counter: int = 0

    while True:
        chat_history = await get_chat_history(client, bot_entity)

        status: int = await safe_handle(chat_history.messages[0], bot_entity, url_set, web_driver_manager)
        time.sleep(5)

        if status == 1:
            sorry_message_counter = 0
        elif status == -1:
            web_driver_manager.close_web_driver()
            break
        elif status == 0:
            sorry_message_counter += 1
        else:
            logging.info(f"Unknown status: {status}")
            web_driver_manager.close_web_driver()
            break

        if sorry_message_counter > 3:
            logging.info("4 'sorry messages' in a row. Stopping...")
            web_driver_manager.close_web_driver()
            break


if __name__ == "__main__":
    logging.basicConfig(filename='bot.log', level=logging.INFO)
    logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

    sessions, dev_mode, port = console_arguments(unix_options=UNIX_OPTIONS, gnu_options=GNU_OPTIONS)

    for session in sessions:
        logging.info(f"Session {session} has been started!")
        client: TelegramClient
        with TelegramClient(session=session, api_id=API_ID, api_hash=API_HASH) as client:
            client.loop.run_until_complete(run(dev_mode=dev_mode, selenium_port=port))
