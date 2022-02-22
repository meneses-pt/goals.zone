import timeit
from datetime import date, timedelta, datetime
from itertools import chain

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.views import generic
from rest_framework import generics

from africa.models import AfricaMatch
from matches.models import Match, Team
from matches.serializers import MatchSerializer, TeamSerializer
from matches.utils import localize_date


class AfricaMatchesHistoryListView(generic.ListView):
    template_name = 'africa/matches/match_history_list.html'

    def get_queryset(self):
        try:
            query_date_str = self.request.GET.get('date')
            query_date_obj = datetime.strptime(query_date_str, '%Y-%m-%d')
            start_date = query_date_obj
            end_date = query_date_obj + timedelta(days=1)
        except (ValueError, TypeError):
            start_date = datetime.combine(datetime.today(), datetime.min.time())
            end_date = start_date + timedelta(days=1)
        start_date = localize_date(start_date)
        end_date = localize_date(end_date)
        return Match.objects.filter(
            id__in=AfricaMatch.objects.values_list('match_id', flat=True),
            datetime__gte=start_date,
            datetime__lt=end_date,
            score__isnull=False
        ) \
            .distinct() \
            .order_by('datetime')

    def get_context_data(self, **kwargs):
        context = super(AfricaMatchesHistoryListView, self).get_context_data(**kwargs)
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


class AfricaMatchesListView(generic.ListView):
    model = Match
    template_name = 'africa/matches/match_list.html'
    context_object_name = 'match_list'
    paginate_by = 50

    def get_queryset(self):
        start = timeit.default_timer()
        qs = Match.objects.filter(
            id__in=AfricaMatch.objects.values_list('match_id', flat=True),
            score__isnull=False
        ) \
            .distinct() \
            .order_by('-datetime')
        end = timeit.default_timer()
        print(end - start)
        return qs


class AfricaMatchDetailView(generic.DetailView):
    template_name = 'africa/matches/match_detail.html'
    model = Match


class AfricaTeamsListView(generic.ListView):
    template_name = 'africa/matches/team_list.html'
    paginate_by = 25

    def get_queryset(self):
        return Team.objects.raw('''
                    select t.id, t.name, t.logo_url, t.logo_file, t.name_code, count(m.id) as matches_count
                    from matches_team t
                    inner join matches_match m on t.id = m.home_team_id or t.id = m.away_team_id
                    inner join africa_match am on m.id = am.match_id
                    group by t.id, name, logo_url, logo_file, name_code
                    order by matches_count desc
                ''')


class AfricaTeamsDetailView(generic.DetailView):
    template_name = 'africa/matches/team_detail.html'
    paginate_by = 25
    model = Team

    def get_context_data(self, **kwargs):
        context = super(AfricaTeamsDetailView, self).get_context_data(**kwargs)
        home_matches = self.object.home_team.all()
        away_matches = self.object.away_team.all()
        team_matches = sorted(chain(home_matches, away_matches), key=lambda instance: instance.datetime, reverse=True)
        paginator = Paginator(team_matches, self.paginate_by)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        context['page_obj'] = page_obj
        return context


class AfricaMatchSearchView(generics.ListAPIView):
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
        start_date = localize_date(start_date)
        end_date = localize_date(end_date)
        queryset = Match.objects.filter(
            id__in=AfricaMatch.objects.values_list('match_id', flat=True),
            datetime__gte=start_date,
            datetime__lte=end_date).distinct().order_by('datetime')
        if filter_q is not None:
            queryset = queryset.filter(
                Q(home_team__name__unaccent__icontains=filter_q) | Q(away_team__name__unaccent__icontains=filter_q))
        return queryset


class AfricaMatchWeekSearchView(generics.ListAPIView):
    serializer_class = MatchSerializer

    def get_queryset(self):
        filter_q = self.request.query_params.get('filter', None)
        start_date = datetime.combine(datetime.today(), datetime.min.time()) - timedelta(days=7)
        start_date = localize_date(start_date)
        queryset = Match.objects.filter(
            id__in=AfricaMatch.objects.values_list('match_id', flat=True),
            datetime__gte=start_date
        ).distinct().order_by('-datetime')
        if filter_q is not None:
            queryset = queryset.filter(
                Q(home_team__name__unaccent__icontains=filter_q) | Q(away_team__name__unaccent__icontains=filter_q))
        return queryset


class AfricaTeamSearchView(generics.ListAPIView):
    serializer_class = TeamSerializer

    def get_queryset(self):
        filter_q = self.request.query_params.get('filter', None)
        query_string = ''' select t.id, t.name, t.logo_url, t.logo_file, t.name_code, count(m.id) as matches_count
                           from matches_team t
                           inner join matches_match m on t.id = m.home_team_id or t.id = m.away_team_id
                           inner join africa_match am on m.id = am.match_id ''' + (
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
