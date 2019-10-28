from django.http import HttpResponse
from datetime import date, timedelta
from django.template import loader
from django.views import generic

from .models import Match


class MatchesListView(generic.ListView):

    def get_queryset(self):
        return Match.objects.order_by('datetime').filter(datetime__gte=date.today() - timedelta(days=3),
                                                         datetime__lte=date.today() + timedelta(days=1))


class MatchDetailView(generic.DetailView):
    model = Match
