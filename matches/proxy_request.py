import json
import logging
from urllib.parse import quote

import requests
from fake_headers import Headers
from fp.fp import FreeProxy
from requests import Response
from scrapfly import ScrapeConfig, ScrapflyClient

from goals_zone import settings
from goals_zone.settings import SCRAPFLY_API_KEY

logger = logging.getLogger(__name__)


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
        self.scrapfly = ScrapflyClient(key=SCRAPFLY_API_KEY)

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
        scrapfly_attempts = 0
        exception_messages = ""
        while (response is None or response.status_code != 200) and attempts < max_attempts:
            # Make one third of the attempts with each strategy
            if use_proxy:
                if (
                    attempts < (max_attempts / 3)
                    and settings.PREMIUM_PROXY
                    and settings.PREMIUM_PROXY != ""
                ):
                    # Temporaryli disable this proxy because of problems with it

                    # ports_list = [12322, 12323, 22323]
                    # # Ports from 11200 to 11250
                    # for i in range(11200, 11251):
                    #     ports_list.append(i)
                    # proxy = settings.PREMIUM_PROXY[:-5] + str(random.choice(ports_list))
                    # self.current_proxy = proxy

                    # Alternative use scrapfly for now
                    self.current_proxy = None
                    scrapfly_attempts += 1
                elif attempts < (max_attempts * 2 / 3) and scrapfly_attempts < 3:
                    # Use Scrapfly. Scrpfly does various attempts that can take almost
                    # 3 minutes each, so we will only allow 3 scrapfly attempts
                    self.current_proxy = None  # Scrapfly
                    scrapfly_attempts += 1
                else:
                    self.current_proxy = FreeProxy(rand=True).get()
            try:
                logger.info(
                    f"Proxy {'Scrapfly' if self.current_proxy is None else self.current_proxy} | "
                    f"Attempt {attempts + 1}",
                )
                attempts += 1
                if use_proxy:
                    if self.current_proxy is None:  # Scrapfly
                        response = self.make_scrapfly_request(url, headers)
                    else:
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
            except Exception as ex:
                exception_messages += str(ex) + "\n"
                logger.warning(
                    f"Exception making ProxyRequest"
                    f" ({attempts}/{max_attempts}): {str(ex)} | {url} | {json.dumps(headers)}",
                )
                headers = Headers(headers=True).generate()
                headers["Accept-Encoding"] = "gzip,deflate,br"
                headers["Referer"] = "https://www.sofascore.com/"
                pass
        if attempts == max_attempts:
            logger.info(f"Number of attempts exceeded trying to make request: {url}")
            raise Exception(
                "Number of attempts exceeded trying to make request: "
                + str(url)
                + "\n"
                + exception_messages
            )
        return response

    def make_scrapfly_request(self, url, headers):
        api_response = self.scrapfly.scrape(
            scrape_config=ScrapeConfig(url=url, headers=headers, asp=True)
        )
        upstream_response = api_response.upstream_result_into_response()
        if not upstream_response:
            raise Exception(
                "No upstream response: [API] "
                + str(api_response.status_code)
                + "|"
                + str(api_response.content)
            )
        if api_response.status_code != 200 or upstream_response.status_code != 200:
            raise Exception(
                "Wrong Status Code: [Upstream] "
                + str(upstream_response.status_code)
                + "|"
                + str(upstream_response.content)
                + "--- [API] "
                + str(api_response.status_code)
                + "|"
                + str(api_response.content)
            )
        return upstream_response

    # Use if scrapfly sdk is not working properly
    @staticmethod
    def make_scrapfly_request_raw(url, headers, timeout):
        original_url = quote(url, safe="")
        headers_str = ""
        for headers_key in headers:
            headers_str += (
                f"&headers[{quote(headers_key, safe='')}]={quote(headers[headers_key], safe='')}"
            )
        url = (
            f"https://api.scrapfly.io/scrape"
            f"?key={SCRAPFLY_API_KEY}"
            f"&asp=true"
            f"&url={original_url}"
        )
        url += headers_str
        response = requests.get(url, headers=headers, timeout=timeout)
        if response.status_code != 200 or response.json()["result"]["status_code"] != 200:
            raise Exception(
                "Wrong Status Code: [Upstream] "
                + str(response.json()["result"]["status_code"])
                + "|"
                + str(response.json()["result"]["content"])
                + "--- [API] "
                + str(response.status_code)
                + "|"
                + str(response.content)
            )
        resp = Response()
        resp_result = response.json()["result"]
        str_content = resp_result["content"]
        str_encoding = resp_result["content_encoding"]
        resp._content = str_content.encode(str_encoding)
        resp.status_code = resp_result["status_code"]
        return resp
