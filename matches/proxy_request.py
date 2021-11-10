import random

import requests
from proxy_list import ProxyList

from matches.utils import get_all_proxies


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
        proxies = None
        while (response is None or response.status_code != 200) and attempts < max_attempts:
            if attempts > 0 or not self.current_proxy:
                print(f"Proxy {self.current_proxy} | Attempt {attempts+1}", flush=True)
                if not proxies:
                    print("Getting proxies", flush=True)
                    # Proxies ---> Alternative 1 (https://github.com/meetsohail/proxy-list)
                    pl = ProxyList()
                    pl_proxies = pl.get_all_proxies()
                    proxies = [f'{p[0]}:{p[1]}' for p in pl_proxies]
                    # Proxies ---> Alternative 2 (Custom)
                    # proxies = get_all_proxies()
                    # End proxies
                    print(str(len(proxies)) + " proxies returned. Going to fetch url.", flush=True)
                self.current_proxy = random.choice(proxies)
                proxies.remove(self.current_proxy)
            try:
                attempts += 1
                if use_proxy:
                    response = requests.get(
                        url,
                        proxies={"https": f'http://{self.current_proxy}'},
                        headers=headers,
                        timeout=timeout
                    )
                else:
                    response = requests.get(
                        url,
                        headers=headers,
                        timeout=timeout
                    )
                if response.status_code != 200:
                    raise Exception("Wrong Status Code: " + str(response.status_code))
            except Exception as e:
                print(f"Exception making ProxyRequest ({attempts}/{max_attempts}): {str(e)}", flush=True)
                pass
        if attempts == max_attempts:
            print("Number of attempts exceeded trying to make request: " + str(url), flush=True)
        return response
