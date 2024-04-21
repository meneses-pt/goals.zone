import base64
import json
import logging
import random
import re
import string
from datetime import datetime

import requests
from django.utils import timezone
from fake_headers import Headers
from lxml.html import fromstring

logger = logging.getLogger(__name__)


def random_string(length: int) -> str:
    letters = string.ascii_lowercase
    return "".join(random.choice(letters) for _ in range(length))


def localize_date(date: datetime) -> datetime:
    try:
        current_timezone = timezone.get_current_timezone()
        date = current_timezone.localize(date)
    except Exception as ex:
        logger.error(f"Exception localizing date ({ex})")
    return date


def get_proxies_sslproxies() -> list[str]:
    url = "https://sslproxies.org/"
    try:
        response = requests.get(url)
    except requests.exceptions.ConnectionError:
        logger.warning(f"Connection error getting proxies ({url})")
        return []
    try:
        parser = fromstring(response.text)
        proxies = []
        for i in parser.xpath("//tbody/tr")[:20]:
            if i.xpath('.//td[7][contains(text(),"yes")]'):
                # Grabbing IP and corresponding PORT
                proxy = ":".join([i.xpath(".//td[1]/text()")[0], i.xpath(".//td[2]/text()")[0]])
                proxies.append(proxy)
    except Exception as ex:
        logger.warning(f"Error getting proxies ({url}): {ex}")
        return []
    return proxies


def get_proxies_freeproxycz() -> list[str]:
    headers_list = Headers(headers=True).generate()
    headers_list["Accept-Encoding"] = "gzip,deflate,br"
    url = "http://free-proxy.cz/en/proxylist/country/all/https/ping/level1"
    try:
        response = requests.get(url, headers=headers_list)
    except requests.exceptions.ConnectionError:
        logger.warning(f"Connection error getting proxies ({url})")
        return []
    try:
        parser = fromstring(response.text)
        proxies = []
        for i in parser.xpath("//table[@id='proxy_list']/tbody/tr")[:20]:
            if not i.xpath('.//td[@colspan="11"]'):
                # Grabbing IP and corresponding PORT
                ip_script = i.xpath("./td[1]/script/text()")[0]
                p = re.compile('"(.*)"')
                res = p.search(ip_script)
                ip_base64 = res.group(1)
                ip = base64.b64decode(ip_base64).decode("utf-8")
                port = i.xpath("./td[2]/span/text()")[0]
                proxy = ":".join([ip, port])
                proxies.append(proxy)
    except Exception as ex:
        logger.warning(f"Error getting proxies ({url}): {ex}")
        return []
    return proxies


def get_proxies_proxyscrape() -> list[str]:
    headers_list = Headers(headers=True).generate()
    headers_list["Accept-Encoding"] = "gzip,deflate,br"
    url = (
        "https://api.proxyscrape.com/"
        "?request=displayproxies&proxytype=http&timeout=10000&country=all&ssl=yes&anonymity=elite"
    )
    try:
        response = requests.get(url, headers=headers_list)
    except requests.exceptions.ConnectionError:
        logger.warning(f"Connection error getting proxies ({url})")
        return []
    try:
        proxies = response.text.splitlines()[:20]
    except Exception as ex:
        logger.warning(f"Error getting proxies ({url}): {ex}")
        return []
    return proxies


def get_proxies_proxylist() -> list[str]:
    url = "https://www.proxy-list.download/api/v0/get?l=en&t=https"
    try:
        response = requests.get(url)
    except requests.exceptions.ConnectionError:
        logger.warning(f"Connection error getting proxies ({url})")
        return []
    try:
        proxies = []
        res = json.loads(response.text)
        for p in res[0]["LISTA"]:
            proxies.append(":".join([p["IP"], p["PORT"]]))
    except Exception as ex:
        logger.warning(f"Error getting proxies ({url}): {ex}")
        return []
    return proxies[:20]


def get_proxies_proxynova() -> list[str]:
    url = "https://www.proxynova.com/proxy-server-list/elite-proxies/"
    try:
        response = requests.get(url)
    except requests.exceptions.ConnectionError:
        logger.warning(f"Connection error getting proxies ({url})")
        return []
    try:
        parser = fromstring(response.text)
        proxies = []
        for i in parser.xpath("//tbody/tr")[:20]:
            ip_script = i.xpath("./td[1]/abbr/script/text()")
            if len(ip_script) > 0:
                ip_script = ip_script[0]
            else:
                continue
            p = re.compile("'(.*)'")
            res = p.search(ip_script)
            if res is None:
                continue
            ip = res.group(1)
            # Grabbing IP and corresponding PORT
            proxy = ":".join([ip, "".join(i.xpath(".//td[2]/text()")[0].split())]).replace("' + '", "")
            proxies.append(proxy)
    except Exception as ex:
        logger.warning(f"Error getting proxies ({url}): {ex}")
        return []
    return proxies


def get_all_proxies() -> list[str]:
    proxies = []
    proxies += get_proxies_sslproxies()
    proxies += get_proxies_freeproxycz()
    proxies += get_proxies_proxyscrape()
    proxies += get_proxies_proxylist()
    proxies += get_proxies_proxynova()
    proxies = list(set(proxies))
    return proxies
