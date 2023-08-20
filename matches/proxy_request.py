import json
import random

import cloudscraper
from fake_headers import Headers
from fp.fp import FreeProxy

from goals_zone import settings
from goals_zone.settings import CAPSOLVER_API_KEY


class ProxyRequest:
    __instance__ = None
    current_proxy = None
    scraper = None

    def __init__(self):
        """
        Constructor.
        """
        if ProxyRequest.__instance__ is None:
            ProxyRequest.__instance__ = self
        else:
            raise Exception("You cannot create another ProxyRequest class")
        self.scraper = cloudscraper.create_scraper(
            captcha={"provider": "capsolver", "api_key": CAPSOLVER_API_KEY}
        )

    @staticmethod
    def get_instance():
        """
        Static method to fetch the current instance.
        """
        if not ProxyRequest.__instance__:
            ProxyRequest()
        return ProxyRequest.__instance__

    def make_request(self, url, headers=None, timeout=10, max_attempts=10, use_proxy=True):
        if headers is None:
            headers = {}
        response = None
        attempts = 0
        while (response is None or response.status_code != 200) and attempts < max_attempts:
            # Make half of the attempts with the PREMIUM_PROXY
            if (
                attempts < (max_attempts / 2)
                and settings.PREMIUM_PROXY
                and settings.PREMIUM_PROXY != ""
            ):
                ports_list = [12322, 12323, 22323]
                # Ports from 11200 to 11250
                for i in range(11200, 11251):
                    ports_list.append(i)
                proxy = settings.PREMIUM_PROXY[:-5] + str(random.choice(ports_list))
                self.current_proxy = proxy
            else:
                self.current_proxy = FreeProxy(rand=True).get()
            try:
                print(f"Proxy {self.current_proxy} | Attempt {attempts + 1}", flush=True)
                attempts += 1
                if use_proxy:
                    response = self.scraper.get(
                        url,
                        proxies={"https": f"http://{self.current_proxy}"},
                        headers=headers,
                        timeout=timeout,
                    )
                else:
                    response = self.scraper.get(url, headers=headers, timeout=timeout)
                if response.status_code != 200:
                    raise Exception(
                        "Wrong Status Code: "
                        + str(response.status_code)
                        + "|"
                        + str(response.content)
                    )
            except Exception as e:
                print(
                    f"Exception making ProxyRequest"
                    f" ({attempts}/{max_attempts}): {str(e)}\n{url}\n{json.dumps(headers)}",
                    flush=True,
                )
                headers = Headers(headers=True).generate()
                headers["Accept-Encoding"] = "gzip,deflate,br"
                headers["Referer"] = "https://www.sofascore.com/"
                pass
        if attempts == max_attempts:
            print(
                "Number of attempts exceeded trying to make request: " + str(url),
                flush=True,
            )
            raise Exception("Number of attempts exceeded trying to make request: " + str(url))
        return response
