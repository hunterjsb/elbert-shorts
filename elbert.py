from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.chrome.options import Options

from webdriver_manager.chrome import ChromeDriverManager

from reticker import TickerExtractor

from collections import Counter
import json
import time

with open('resource/secrets.json', 'r') as s_f:
    credentials = json.load(s_f)


class Elbert:
    def __init__(self, user_credentials: dict or None):
        # Use the `install()` method to set `executable_path` in a new `Service` instance:
        if user_credentials:  # pass None to `user_credentials` if you don't want to use the WebDriver
            service = Service(executable_path=ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service,
                                           options=self._build_options(),
                                           desired_capabilities=self._build_caps())

            self.email = user_credentials['email']
            self.password = user_credentials['password']
            self.online = True
        else:
            self.driver = None

        self.logged_in = False
        self.msg_cache = []

        self.common_phrases = ['IPO', 'ITM', 'OTM', 'BETA', 'GAMMA', 'THETA', 'EPS', 'AM', 'PM', 'USD', 'AH', 'HALTED'
                               'EST', 'UK', 'RIP', 'HTB', 'IMO', 'OTC', 'FDA', 'FED', 'EOD', 'DD']

    @staticmethod
    def _build_options():
        """create Options object to pass to ChromeDriver"""
        opts = Options()
        opts.add_argument("auto-select-tab-capture-source-by-title=Screen 1")  # doesn't work
        opts.add_experimental_option('prefs', {'profile.default_content_setting_values.media_stream_mic': 1})  # mic
        return opts

    @staticmethod
    def _build_caps():
        """create DesiredCapabilities object to pass to ChromeDriver"""
        caps = DesiredCapabilities.CHROME
        caps['goog:loggingPrefs'] = {'performance': 'ALL'}
        return caps

    def login(self):
        """logs into Discord"""
        self.driver.get('https://discord.com/login')

        # enter credentials
        email_input = self.driver.find_element(By.NAME, 'email')
        password_input = self.driver.find_element(By.NAME, 'password')
        email_input.send_keys(self.email)
        password_input.send_keys(self.password)

        # click login
        self.driver.find_element(By.XPATH, '//*[@id="app-mount"]/div[2]/div/div/div/div/form/div/div/div[1]/div[2]/'
                                           'button[2]/div').click()
        self.logged_in = True

    def join_atlas(self):
        """join atlas trading text channel, trading floor 1"""
        nsfw_continue_button = '//*[@id="app-mount"]/div[2]/div/div[2]/div/div/div/div[2]/div[3]/div[2]/div[1]/' \
                               'div[1]/div/div[4]/button[2]'  # problem child

        if not self.logged_in:
            self.login()
        time.sleep(3)  # replace with webdriver EC
        self.driver.get('https://discord.com/channels/428232997737594901/697135489484062762')  # xan nation

        # DEPRECATED CODE - Atlas removed NSFW accept button
        # WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, nsfw_continue_button)))
        # time.sleep(1)  # replace with try... except above - click sometimes get interrupted
        # self.driver.find_element(By.XPATH, nsfw_continue_button).click()

    def _get_logs(self):
        """extract http requests from logs"""
        logs_raw = self.driver.get_log("performance")
        logs = [json.loads(lr["message"])["message"] for lr in logs_raw]
        return logs

    @staticmethod
    def log_filter(log_data):
        """used when determining which logs are responses"""
        return (
            # is an actual response
            log_data["method"] == "Network.responseReceived"
            # and json
            and "json" in log_data["params"]["response"]["mimeType"]
        )

    def _save_cache(self):
        with open('resource/msg_cache.json', 'w') as f:
            json.dump(self.msg_cache, f, indent=4)

    def _load_cache(self):
        with open('resource/msg_cache.json') as f:
            self.msg_cache = json.load(f)
        return self.msg_cache

    def load_messages(self):
        """
        request logs then get responses for the messages.
        saves the last 50 messages retrieved.
        if Elbert is offline it will load the saved cache.
        """
        if not self.driver:
            return self._load_cache()

        self.join_atlas()
        # TODO FIX THIS
        time.sleep(5)

        responses = []
        _logs = self._get_logs()
        for _log in filter(self.log_filter, _logs):
            request_id = _log["params"]["requestId"]
            resp_url = _log["params"]["response"]["url"]
            print(f"Caught {resp_url}")
            if 'messages' in resp_url:
                msg_cache = self.driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": request_id})['body']
                self.msg_cache = json.loads(msg_cache)
                responses.append(self.msg_cache)

        self._save_cache()
        return responses

    def parse_cache(self, parser: TickerExtractor):
        tickers_ = []
        for i, msg in enumerate(self.msg_cache):
            msg_tickers = parser.extract(msg['content'])
            self.msg_cache[i]['tickers'] = msg_tickers
            tickers_ += msg_tickers

        tickers_ = Counter(tickers_)
        for phrase in self.common_phrases:
            if phrase in tickers_:
                tickers_.pop(phrase)

        self._save_cache()
        return tickers_


########################################################################################################################
if __name__ == "__main__":

    # join: atlas trading / trading floor 1
    elbert = Elbert(credentials)

    # open the messages
    elbert.load_messages()
    tickers = elbert.parse_cache(TickerExtractor())  # Counter by default
    print(tickers)
