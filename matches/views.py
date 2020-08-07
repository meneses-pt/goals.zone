from datetime import date, timedelta, datetime

from django.db.models import Q
from django.utils import timezone
from django.views import generic
from rest_framework import generics

from .models import Match
from .serializers import MatchSerializer


class MatchesListView(generic.ListView):

    def get_queryset(self):
        try:
            query_date_str = self.request.GET.get('date')
            query_date_obj = datetime.strptime(query_date_str, '%Y-%m-%d')
            start_date = query_date_obj
            end_date = query_date_obj + timedelta(days=1)
        except (ValueError, TypeError):
            start_date = datetime.combine(datetime.today(), datetime.min.time())
            end_date = start_date + timedelta(days=1)
        start_date = timezone.get_current_timezone().localize(start_date)
        end_date = timezone.get_current_timezone().localize(end_date)
        return Match.objects.order_by('datetime').filter(datetime__gte=start_date,
                                                         datetime__lte=end_date,
                                                         videogoal__isnull=False).distinct()

    def get_context_data(self, **kwargs):
        context = super(MatchesListView, self).get_context_data(**kwargs)
        try:
            query_date_str = self.request.GET.get('date')
            query_date_obj = datetime.strptime(query_date_str, '%Y-%m-%d')
        except (ValueError, TypeError):
            query_date_obj = datetime.today()
        context['date'] = query_date_obj
        if query_date_obj.date() < date.today():
            context['date_next'] = query_date_obj + timedelta(days=1)
        context['date_prev'] = query_date_obj - timedelta(days=1)
        return context


class MatchDetailView(generic.DetailView):
    model = Match


class MatchSearchView(generics.ListAPIView):
    serializer_class = MatchSerializer

    def get_queryset(self):
        query_date_str = self.request.query_params.get('date', None)
        filter_q = self.request.query_params.get('filter', None)
        try:
            query_date_obj = datetime.strptime(query_date_str, '%Y-%m-%d')
            start_date = query_date_obj
            end_date = query_date_obj + timedelta(days=1)
        except (ValueError, TypeError):
            start_date = datetime.combine(datetime.today(), datetime.min.time())
            end_date = start_date + timedelta(days=1)
        start_date = timezone.get_current_timezone().localize(start_date)
        end_date = timezone.get_current_timezone().localize(end_date)
        queryset = Match.objects.order_by('datetime').filter(datetime__gte=start_date,
                                                             datetime__lte=end_date,
                                                             videogoal__isnull=False).distinct()
        if filter_q is not None:
            queryset = queryset.filter(
                Q(home_team__name__unaccent__icontains=filter_q) | Q(away_team__name__unaccent__icontains=filter_q))
        return queryset
