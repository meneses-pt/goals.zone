from django.db import models


class Log(models.Model):
    class Meta:
        managed = False
        permissions = (("can_view_logs", "Can view logs"),)
