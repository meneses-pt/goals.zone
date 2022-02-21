from datetime import date, timedelta, datetime
from itertools import chain

from django.core.paginator import Paginator
from django.db.models import Count
from django.views import generic

from matches.models import Match, Team
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
        return Match.objects.order_by('datetime').filter(datetime__gte=start_date,
                                                         datetime__lt=end_date,
                                                         videogoal__isnull=False).distinct()

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
        return Match.objects.order_by('-datetime').filter(videogoal__isnull=False).distinct()


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
                    inner join matches_videogoal vg on m.id = vg.match_id
                    group by t.id, name, logo_url, logo_file, name_code
                    order by matches_count desc
                ''')


class AfricaTeamsDetailView(generic.DetailView):
    template_name = 'africa/matches/team_detail.html'
    paginate_by = 25
    model = Team

    def get_context_data(self, **kwargs):
        context = super(AfricaTeamsDetailView, self).get_context_data(**kwargs)
        home_matches = self.object.home_team.annotate(vg_count=Count('videogoal')).filter(vg_count__gt=0)
        away_matches = self.object.away_team.annotate(vg_count=Count('videogoal')).filter(vg_count__gt=0)
        team_matches = sorted(chain(home_matches, away_matches), key=lambda instance: instance.datetime, reverse=True)
        paginator = Paginator(team_matches, self.paginate_by)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        context['page_obj'] = page_obj
        return context
