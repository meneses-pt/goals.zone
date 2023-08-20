import json
import random

import cloudscraper
import requests
from fake_headers import Headers
from fp.fp import FreeProxy

from goals_zone import settings


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
        self.scraper = cloudscraper.create_scraper()

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
                ports_list = [
                    12322,
                    12323,
                    22323,
                    11200,
                    11201,
                    11202,
                    11203,
                    11204,
                    11205,
                    11206,
                    11207,
                    11208,
                    11209,
                    11210,
                    11211,
                    11212,
                    11213,
                    11214,
                    11215,
                    11216,
                    11217,
                    11218,
                    11219,
                    11220,
                    11221,
                    11222,
                    11223,
                    11224,
                    11225,
                    11226,
                    11227,
                    11228,
                    11229,
                    11230,
                    11231,
                    11232,
                    11233,
                    11234,
                    11235,
                    11236,
                    11237,
                    11238,
                    11239,
                    11240,
                    11241,
                    11242,
                    11243,
                    11244,
                    11245,
                    11246,
                    11247,
                    11248,
                    11249,
                    11250,
                ]
                proxy = settings.PREMIUM_PROXY[:-5] + str(random.choice(ports_list))
                self.current_proxy = proxy
            else:
                self.current_proxy = FreeProxy(rand=True).get()
            try:
                print(f"Proxy {self.current_proxy} | Attempt {attempts + 1}", flush=True)
                attempts += 1
                if use_proxy:
                    response = requests.get(
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
                pass
        if attempts == max_attempts:
            print(
                "Number of attempts exceeded trying to make request: " + str(url),
                flush=True,
            )
            raise Exception("Number of attempts exceeded trying to make request: " + str(url))
        return response
