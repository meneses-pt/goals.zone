from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from background_task.models import Task

from matches.goals_populator import fetch_videogoals
from matches.matches_populator import fetch_new_matches
from goals_zone import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('matches.urls'))
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if not Task.objects.filter(verbose_name="fetch_new_matches").exists():
    fetch_new_matches(repeat=60 * 5, repeat_until=None, verbose_name="fetch_new_matches")

if not Task.objects.filter(verbose_name="fetch_videogoals").exists():
    fetch_videogoals(repeat=60, repeat_until=None, verbose_name="fetch_videogoals")
