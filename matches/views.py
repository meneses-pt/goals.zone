from datetime import date, timedelta, datetime
from itertools import chain

from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from django.views import generic
from rest_framework import generics

from .models import Match, Team
from .serializers import MatchSerializer, TeamSerializer


class MatchesListView(generic.ListView):
    template_name = 'matches/match_list.html'

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
    template_name = 'matches/match_detail.html'
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


class TeamsListView(generic.ListView):
    template_name = 'matches/team_list.html'
    paginate_by = 25

    def get_queryset(self):
        return Team.objects.raw('''
                    select t.id, t.name, t.logo_url, t.logo_file, t.name_code, count(m.id) as matches_count
                    from matches_team t
                    inner join matches_match m on t.id = m.home_team_id or t.id = m.away_team_id
                    inner join matches_videogoal vg on m.id = vg.match_id
                    group by t.id, name, logo_url, logo_file, name_code
                    order by matches_count desc
                ''')


class TeamsDetailView(generic.DetailView):
    template_name = 'matches/team_detail.html'
    paginate_by = 25
    model = Team

    def get_context_data(self, **kwargs):
        context = super(TeamsDetailView, self).get_context_data(**kwargs)
        # home_matches = self.object.home_team.all()
        # away_matches = self.object.away_team.all()
        home_matches = self.object.home_team.annotate(vg_count=Count('videogoal')).filter(vg_count__gt=0)
        away_matches = self.object.away_team.annotate(vg_count=Count('videogoal')).filter(vg_count__gt=0)
        team_matches = sorted(chain(home_matches, away_matches), key=lambda instance: instance.datetime, reverse=True)
        paginator = Paginator(team_matches, self.paginate_by)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        context['page_obj'] = page_obj
        return context


class TeamSearchView(generics.ListAPIView):
    serializer_class = TeamSerializer

    def get_queryset(self):
        filter_q = self.request.query_params.get('filter', None)
        query_string = ''' select t.id, t.name, t.logo_url, t.logo_file, t.name_code, count(m.id) as matches_count
                           from matches_team t
                           inner join matches_match m on t.id = m.home_team_id or t.id = m.away_team_id
                           inner join matches_videogoal vg on m.id = vg.match_id ''' + (
            '' if filter_q is None
            else
            f''
            f'where UPPER(UNACCENT(t.name)::text) '
            f'LIKE \'%%\' || UPPER(UNACCENT(\'{filter_q}\')::text) || \'%%\''
        ) + '''
                            group by t.id, name, logo_url, logo_file, name_code
                            order by matches_count desc
                        '''
        queryset = Team.objects.raw(query_string)
        return queryset
