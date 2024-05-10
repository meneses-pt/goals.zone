from __future__ import annotations

import asyncio
import json
import logging
import random
from io import BytesIO
from urllib.parse import quote

import aiohttp
import pycurl
import requests
from fake_headers import Headers
from fp.fp import FreeProxy
from requests.structures import CaseInsensitiveDict
from scrapfly import ScrapeConfig, ScrapflyClient

from goals_zone import settings
from goals_zone.settings import SCRAPFLY_API_KEY
from monitoring.models import MonitoringAccount

logger = logging.getLogger(__name__)


class ProxyRequest:
    __instance__ = None
    current_proxy = None
    scraper = None

    def __init__(self) -> None:
        """
        Constructor.
        """
        if ProxyRequest.__instance__ is None:
            ProxyRequest.__instance__ = self
        else:
            raise Exception("You cannot create another ProxyRequest class")
        self.scrapfly = ScrapflyClient(key=SCRAPFLY_API_KEY)

    @staticmethod
    def get_instance() -> ProxyRequest:
        """
        Static method to fetch the current instance.
        """
        if not ProxyRequest.__instance__:
            ProxyRequest()
        return ProxyRequest.__instance__  # type: ignore

    @staticmethod
    def _send_proxy_response_heartbeat() -> None:
        try:
            monitoring_accounts = MonitoringAccount.objects.all()
            for ma in monitoring_accounts:
                if ma.proxy_heartbeat:
                    requests.get(ma.proxy_heartbeat)
        except Exception as ex:
            logger.error(f"Error sending monitoring message: {ex}")

    def make_request(
        self,
        url: str,
        headers: dict | None = None,
        timeout: int = 10,
        max_attempts: int = 10,
        use_proxy: bool = True,
        use_unsafe: bool = False,
    ) -> requests.Response | None:
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
                    and (use_unsafe or not settings.REQUESTS_SAFE_MODE)
                ):
                    # This might be unsafe for data requests because of
                    # fingerprinting of the client libs (They are returning random data)
                    # Requests will come here if they are non-data requests (like images), which can `user_unsafe`
                    # or if the `REQUESTS_SAFE_MODE` is disabled,
                    # which means the current client is not fingerprinted yet

                    # NOTE: In an emergency, use `REQUESTS_SAFE_MODE = True` in settings

                    ports_list = [12322, 12323, 22323]
                    # Ports from 11200 to 11250
                    for i in range(11200, 11251):
                        ports_list.append(i)
                    proxy = settings.PREMIUM_PROXY[:-5] + str(random.choice(ports_list))
                    self.current_proxy = proxy
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
                        # INFO: requests
                        # response = requests.get(
                        #     url,
                        #     proxies={"https": f"http://{self.current_proxy}"},
                        #     headers=headers,
                        #     timeout=timeout,
                        # )

                        # INFO: aiohttp
                        # response = self.make_aiohttp_request(url, headers, timeout)

                        # INFO: pycurl
                        response = self.make_pycurl_request(url, headers, timeout)

                        self._send_proxy_response_heartbeat()
                else:
                    response = requests.get(url, headers=headers, timeout=timeout)
                if response.status_code != 200:
                    raise Exception("Wrong Status Code: " + str(response.status_code) + "|" + str(response.content))
            except Exception as ex:
                exception_messages += str(ex) + "\n"
                logger.warning(
                    f"Exception making ProxyRequest"
                    f" ({attempts}/{max_attempts}): {str(ex)} | {url} | {json.dumps(headers)}",
                )
                headers = dict(Headers(headers=True).generate())
                headers["Accept-Encoding"] = "gzip,deflate,br"
                headers["Referer"] = "https://www.sofascore.com/"
                pass
        if attempts == max_attempts:
            logger.info(f"Number of attempts exceeded trying to make request: {url}")
            raise Exception(
                "Number of attempts exceeded trying to make request: " + str(url) + "\n" + exception_messages
            )
        return response

    def make_scrapfly_request(self, url: str, headers: dict) -> requests.Response:
        api_response = self.scrapfly.scrape(scrape_config=ScrapeConfig(url=url, headers=headers, asp=True))
        upstream_response = api_response.upstream_result_into_response()
        if not upstream_response:
            raise Exception(
                "No upstream response: [API] " + str(api_response.status_code) + "|" + str(api_response.content)
            )
        if api_response.status_code != 200 or upstream_response.status_code != 200:
            if api_response.status_code == 429 or upstream_response.status_code == 429:
                from matches.goals_populator import send_monitoring_message

                send_monitoring_message(
                    "Scrapfly Error Code 429"
                    + str(upstream_response.status_code)
                    + "|"
                    + str(upstream_response.content)
                    + "--- [API] "
                    + str(api_response.status_code)
                    + "|"
                    + str(api_response.content),
                    is_alert=True,
                    disable_notification=False,
                )
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

    def make_aiohttp_request(self, url: str, headers: dict, timeout: int = 10) -> requests.Response:
        async def fetch_data() -> requests.Response:
            async with (
                aiohttp.ClientSession() as session,
                session.get(
                    url,
                    proxy=f"http://{self.current_proxy}",
                    headers=headers,
                    timeout=timeout,
                ) as response,
            ):
                requests_response = requests.Response()
                requests_response.status_code = response.status
                requests_response.headers = CaseInsensitiveDict(response.headers)
                requests_response._content = await response.read()
                requests_response.url = str(response.url)
                requests_response.reason = response.reason or ""
                return requests_response

        loop = asyncio.get_event_loop()
        data = loop.run_until_complete(fetch_data())
        return data

    def make_pycurl_request(self, url: str, headers: dict, timeout: int = 10) -> requests.Response:
        def collect_headers(_header_line: bytes, _headers_dict: dict) -> None:
            # Decode and split the header line into key and value
            header_line = _header_line.decode("iso-8859-1").strip()
            if ":" in header_line:
                key, value = header_line.split(":", 1)
                _headers_dict[key.strip()] = value.strip()

        headers_dict: dict = {}

        buffer = BytesIO()
        c = pycurl.Curl()
        c.setopt(pycurl.URL, url)
        if self.current_proxy is not None:
            proxy_sep = self.current_proxy.split("@")
            c.setopt(pycurl.PROXY, proxy_sep[1])
            c.setopt(pycurl.PROXYUSERPWD, proxy_sep[0])
        c.setopt(pycurl.HTTPHEADER, list(headers))
        c.setopt(pycurl.WRITEDATA, buffer)
        c.setopt(pycurl.HEADERFUNCTION, lambda header_line: collect_headers(header_line, headers_dict))
        c.setopt(pycurl.TIMEOUT, timeout)
        c.perform()
        c.close()

        requests_response = requests.Response()
        requests_response.status_code = c.getinfo(pycurl.HTTP_CODE)
        requests_response.headers = CaseInsensitiveDict(headers_dict)
        requests_response._content = buffer.getvalue()
        requests_response.url = str(c.getinfo(pycurl.EFFECTIVE_URL))
        requests_response.reason = ""
        return requests_response

    # Use if scrapfly sdk is not working properly
    @staticmethod
    def make_scrapfly_request_raw(url: str, headers: dict, timeout: int) -> requests.Response:
        original_url = quote(url, safe="")
        headers_str = ""
        for headers_key in headers:
            headers_str += f"&headers[{quote(headers_key, safe='')}]={quote(headers[headers_key], safe='')}"
        url = f"https://api.scrapfly.io/scrape?key={SCRAPFLY_API_KEY}&asp=true&url={original_url}"
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
        resp = requests.Response()
        resp_result = response.json()["result"]
        str_content = resp_result["content"]
        str_encoding = resp_result["content_encoding"]
        resp._content = str_content.encode(str_encoding)
        resp.status_code = resp_result["status_code"]
        return resp
