import ipaddress
import logging
from typing import Callable

import pytz
from django.contrib.gis.geoip2 import GeoIP2
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from geoip2.errors import AddressNotFoundError

logger = logging.getLogger(__name__)


class TimezoneMiddleware:
    def __init__(self, get_response: Callable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if "HTTP_X_FORWARDED_FOR" in request.META:
            request.META["HTTP_X_PROXY_REMOTE_ADDR"] = request.META["REMOTE_ADDR"]
            parts = request.META["HTTP_X_FORWARDED_FOR"].split(",", 1)
            request.META["REMOTE_ADDR"] = parts[0]
        ip = request.META["REMOTE_ADDR"]
        g = GeoIP2()
        time_zone = None
        try:
            ip = ipaddress.ip_address(ip)
            try:
                ip_response = g.city(str(ip))
                time_zone = ip_response["time_zone"]
            except AddressNotFoundError as ex:
                logger.warning(f"AddressNotFoundError: {ex}")
        except ValueError:
            logger.warning(f"Address/netmask is invalid: {ip}")
        except Exception as ex:
            logger.warning(f"IP: {ip}. Exception: {ex}")
        if time_zone:
            timezone_object = pytz.timezone(time_zone)
            timezone.activate(timezone_object)
        else:
            timezone.deactivate()
        return self.get_response(request)
