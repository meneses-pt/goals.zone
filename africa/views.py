from django.views import generic

from matches.models import Match


class AfricaMatchesListView(generic.ListView):
    model = Match
    template_name = 'africa/matches/match_list.html'
    context_object_name = 'match_list'
    paginate_by = 50

    def get_queryset(self):
        return Match.objects.order_by('-datetime').filter(videogoal__isnull=False).distinct()
