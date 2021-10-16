from django.urls import path

from . import views

urlpatterns = [
    path('', views.MatchesListView.as_view(), name='index'),
    path('infinite', views.MatchesAltListView.as_view(), name='alt'),
    path('<slug:slug>', views.MatchDetailView.as_view(), name='match-detail'),
    path('teams/', views.TeamsListView.as_view(), name='teams-list'),
    path('teams/<slug:slug>', views.TeamsDetailView.as_view(), name='teams-detail'),

    # api
    path('api/matches/', views.MatchSearchView.as_view(), name='api-matches-list'),
    path('api/matches-alt/', views.MatchAltSearchView.as_view(), name='api-matches-list-alt'),
    path('api/teams/', views.TeamSearchView.as_view(), name='api-teams-list'),

    path('api/matches-list/', views.MatchApiListView.as_view(), name='api-matches-list-alt'),
]
