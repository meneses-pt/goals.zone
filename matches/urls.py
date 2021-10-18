from django.urls import path

from . import views

urlpatterns = [
    path('', views.MatchesListView.as_view(), name='index'),
    path('history', views.MatchesHistoryListView.as_view(), name='history'),
    path('<slug:slug>', views.MatchDetailView.as_view(), name='match-detail'),
    path('teams', views.TeamsListView.as_view(), name='teams-list'),
    path('teams/<slug:slug>', views.TeamsDetailView.as_view(), name='teams-detail'),

    # api
    path('api/matches/', views.MatchSearchView.as_view(), name='api-matches-list'),
    path('api/matches-week/', views.MatchWeekSearchView.as_view(), name='api-matches-week-list'),
    path('api/teams/', views.TeamSearchView.as_view(), name='api-teams-list'),
]
