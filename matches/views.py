from django.http import HttpResponse
from datetime import date, timedelta, datetime
from django.template import loader, context
from django.views import generic

from .models import Match


class MatchesListView(generic.ListView):

    def get_queryset(self):
        try:
            query_date_str = self.request.GET.get('date')
            query_date_obj = datetime.strptime(query_date_str, '%Y-%m-%d')
        except Exception as e:
            query_date_obj = date.today()
        return Match.objects.order_by('datetime').filter(datetime__gte=query_date_obj,
                                                         datetime__lte=query_date_obj + timedelta(days=1),
                                                         videogoal__isnull=False).distinct()

    def get_context_data(self, **kwargs):
        context = super(MatchesListView, self).get_context_data(**kwargs)
        try:
            query_date_str = self.request.GET.get('date')
            query_date_obj = datetime.strptime(query_date_str, '%Y-%m-%d')
        except Exception as e:
            query_date_obj = date.today()
        context['date'] = query_date_obj
        context['date_next'] = query_date_obj + timedelta(days=1)
        context['date_prev'] = query_date_obj - timedelta(days=1)
        return context


class MatchDetailView(generic.DetailView):
    model = Match
