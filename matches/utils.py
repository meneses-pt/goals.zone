import base64
import json
import re

import requests
from lxml.html import fromstring

headers_list = {
    'accept': 'text/html,application/xhtml+xml,application/xml;'
              'q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    'accept-encoding': 'gzip, deflate',
    'accept-language': 'pt-PT,pt;q=0.9,en-PT;q=0.8,en;q=0.7,en-US;q=0.6,es;q=0.5,fr;q=0.4',
    'cache-control': 'no-cache',
    'pragma': 'no-cache',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'none',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36'
}


def get_proxies_sslproxies():
    url = 'https://sslproxies.org/'
    try:
        response = requests.get(url)
    except requests.exceptions.ConnectionError:
        print(f'Connection error getting proxies ({url})', flush=True)
        return list()
    try:
        parser = fromstring(response.text)
        proxies = list()
        for i in parser.xpath('//tbody/tr')[:20]:
            if i.xpath('.//td[7][contains(text(),"yes")]'):
                # Grabbing IP and corresponding PORT
                proxy = ":".join([i.xpath('.//td[1]/text()')[0], i.xpath('.//td[2]/text()')[0]])
                proxies.append(proxy)
    except Exception as e:
        print(f'Error getting proxies ({url}): {e}', flush=True)
        return list()
    return proxies


def get_proxies_freeproxycz():
    global headers_list
    url = 'http://free-proxy.cz/en/proxylist/country/all/https/ping/level1'
    try:
        response = requests.get(url, headers=headers_list)
    except requests.exceptions.ConnectionError:
        print(f'Connection error getting proxies ({url})', flush=True)
        return list()
    try:
        parser = fromstring(response.text)
        proxies = list()
        for i in parser.xpath("//table[@id='proxy_list']/tbody/tr")[:20]:
            if not i.xpath('.//td[@colspan="11"]'):
                # Grabbing IP and corresponding PORT
                ip_script = i.xpath('./td[1]/script/text()')[0]
                p = re.compile("\"(.*)\"")
                res = p.search(ip_script)
                ip_base64 = res.group(1)
                ip = base64.b64decode(ip_base64).decode("utf-8")
                port = i.xpath('./td[2]/span/text()')[0]
                proxy = ":".join([ip, port])
                proxies.append(proxy)
    except Exception as e:
        print(f'Error getting proxies ({url}): {e}', flush=True)
        return list()
    return proxies


def get_proxies_proxyscrape():
    global headers_list
    url = 'https://api.proxyscrape.com/?request=displayproxies&proxytype=http&timeout=10000&country=all&ssl=yes&anonymity=elite'
    try:
        response = requests.get(url, headers=headers_list)
    except requests.exceptions.ConnectionError:
        print(f'Connection error getting proxies ({url})', flush=True)
        return list()
    try:
        proxies = response.text.splitlines()[:20]
    except Exception as e:
        print(f'Error getting proxies ({url}): {e}', flush=True)
        return list()
    return proxies


def get_proxies_proxylist():
    url = 'https://www.proxy-list.download/api/v0/get?l=en&t=https'
    try:
        response = requests.get(url)
    except requests.exceptions.ConnectionError:
        print(f'Connection error getting proxies ({url})', flush=True)
        return list()
    try:
        proxies = list()
        res = json.loads(response.text)
        for p in res[0]['LISTA']:
            proxies.append(":".join([p["IP"], p["PORT"]]))
    except Exception as e:
        print(f'Error getting proxies ({url}): {e}', flush=True)
        return list()
    return proxies[:20]


def get_proxies_proxynova():
    url = 'https://www.proxynova.com/proxy-server-list/elite-proxies/'
    try:
        response = requests.get(url)
    except requests.exceptions.ConnectionError:
        print(f'Connection error getting proxies ({url})', flush=True)
        return list()
    try:
        parser = fromstring(response.text)
        proxies = list()
        for i in parser.xpath('//tbody/tr')[:20]:
            ip_script = i.xpath('./td[1]/abbr/script/text()')
            if len(ip_script) > 0:
                ip_script = ip_script[0]
            else:
                continue
            p = re.compile("\'(.*)\'")
            res = p.search(ip_script)
            if res is None:
                continue
            ip = res.group(1)
            # Grabbing IP and corresponding PORT
            proxy = ":".join([ip, ''.join(i.xpath('.//td[2]/text()')[0].split())]).replace("' + '", "")
            proxies.append(proxy)
    except Exception as e:
        print(f'Error getting proxies ({url}): {e}', flush=True)
        return list()
    return proxies


def get_all_proxies():
    proxies = list()
    proxies += get_proxies_sslproxies()
    proxies += get_proxies_freeproxycz()
    proxies += get_proxies_proxyscrape()
    proxies += get_proxies_proxylist()
    proxies += get_proxies_proxynova()
    proxies = list(set(proxies))
    return proxies
