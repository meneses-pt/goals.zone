import pytz
from django.contrib.gis.geoip2 import GeoIP2

from django.utils import timezone
from geoip2.errors import AddressNotFoundError


class TimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if "HTTP_X_FORWARDED_FOR" in request.META:
            request.META["HTTP_X_PROXY_REMOTE_ADDR"] = request.META["REMOTE_ADDR"]
            parts = request.META["HTTP_X_FORWARDED_FOR"].split(",", 1)
            request.META["REMOTE_ADDR"] = parts[0]
        ip = request.META["REMOTE_ADDR"]
        g = GeoIP2()
        try:
            ip_response = g.city(ip)
            time_zone = ip_response['time_zone']
        except AddressNotFoundError:
            time_zone = None
        if time_zone:
            timezone_object = pytz.timezone(time_zone)
            timezone.activate(timezone_object)
        else:
            timezone.deactivate()
        return self.get_response(request)
