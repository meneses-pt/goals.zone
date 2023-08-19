import json

import requests
from fake_headers import Headers
from fp.fp import FreeProxy

from goals_zone import settings


class ProxyRequest:
    __instance__ = None
    current_proxy = None

    def __init__(self):
        """
        Constructor.
        """
        if ProxyRequest.__instance__ is None:
            ProxyRequest.__instance__ = self
        else:
            raise Exception("You cannot create another ProxyRequest class")

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
                self.current_proxy = settings.PREMIUM_PROXY
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
                    response = requests.get(url, headers=headers, timeout=timeout)
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
                headers["Accept-Encoding"] = "gzip, deflate, br"
                pass
        if attempts == max_attempts:
            print(
                "Number of attempts exceeded trying to make request: " + str(url),
                flush=True,
            )
            raise Exception("Number of attempts exceeded trying to make request: " + str(url))
        return response
