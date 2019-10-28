from django.urls import path

from . import views

urlpatterns = [
    path('', views.MatchesListView.as_view(), name='index'),
    path('<int:pk>', views.MatchDetailView.as_view(), name='match-detail'),
]
