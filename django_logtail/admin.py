import json
from os.path import getsize, isfile

from django.contrib import admin
from django.http import Http404, HttpResponse
from django.template.response import TemplateResponse
from django.urls import re_path

from django_logtail import app_settings
from django_logtail.models import Log


class HttpUnauthorized(HttpResponse):
    status_code = 401


class LogAdmin(admin.ModelAdmin):
    class Media:
        js = (
            "admin/js/vendor/jquery/jquery.min.js",
            "logtail/js/logtail.js",
        )
        css = {"all": ("logtail/css/logtail.css",)}

    def has_add_permission(self, request):
        return False

    def log_view(self, request, logfile="", seek_to="0"):
        context = self.log_context(logfile, seek_to)
        return HttpResponse(self.iter_json(context), content_type="application/json")

    def log_context(self, logfile, seek_to):
        context = {}
        seek_to = int(seek_to)
        try:
            log_file = app_settings.LOGTAIL_FILES[logfile]
        except KeyError as exc:
            raise Http404("No such log file") from exc

        try:
            file_length = getsize(log_file)
        except OSError as exc:
            raise Http404("Cannot access file") from exc

        if seek_to > file_length:
            seek_to = file_length

        try:
            with open(log_file) as context["log"]:
                context["log"].seek(seek_to)
                context["starts"] = seek_to
        except OSError as exc:
            raise Http404("Cannot access file") from exc

        return context

    def iter_json(self, context):
        yield '{"starts": "%d","data": "' % context["starts"]

        while True:
            line = context["log"].readline()
            if line:
                yield json.dumps(line).strip('"')
            else:
                yield '", "ends": "%d"}' % context["log"].tell()
                context["log"].close()
                return

    def changelist_view(self, request, extra_context=None):
        context = {
            "title": "Logtail",
            "app_label": self.model._meta.app_label,
            "cl": None,
            "media": self.media,
            "has_add_permission": self.has_add_permission(request),
            "update_interval": app_settings.LOGTAIL_UPDATE_INTERVAL,
            "logfiles": ((li, f) for li, f in app_settings.LOGTAIL_FILES.items() if isfile(f)),
        }

        return TemplateResponse(
            request,
            "logtail/logtail_list.html",
            context,
        )

    def get_urls(self):
        urls = super().get_urls()
        urls.insert(
            0,
            re_path(
                r"^(?P<logfile>[-\w\.]+)/(?P<seek_to>\d+)/$",
                self.admin_site.admin_view(self.log_view),
            ),
        )
        return urls


admin.site.register(Log, LogAdmin)
