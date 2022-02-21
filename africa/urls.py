from django.urls import path

from . import views

urlpatterns = [
    path('', views.AfricaMatchesListView.as_view(), name='index'),
    path('history', views.AfricaMatchesHistoryListView.as_view(), name='history'),
    path('teams', views.AfricaTeamsListView.as_view(), name='teams-list'),

    path('<slug:slug>', views.AfricaMatchDetailView.as_view(), name='match-detail'),
    path('teams/<slug:slug>', views.AfricaTeamsDetailView.as_view(), name='teams-detail'),
]
