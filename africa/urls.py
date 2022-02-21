from django.urls import path

from . import views

urlpatterns = [
    path('', views.AfricaMatchesListView.as_view(), name='index'),
]
