from django import forms
from django.contrib import admin

from .models import Match, VideoGoal, Team, TeamAlias, AffiliateTerm, WebhookUrl


class TeamAdmin(admin.ModelAdmin):
    search_fields = ['name']


class TeamAliasAdmin(admin.ModelAdmin):
    autocomplete_fields = ['team']
    search_fields = ['alias', 'team__name']


class WebhookUrlAdminForm(forms.ModelForm):
    class Meta:
        model = WebhookUrl
        fields = ['description', 'webhook', 'message', 'destination']
        widgets = {
            'message': forms.Textarea(attrs={'cols': 80, 'rows': 3}),
        }


class WebhookUrlAdmin(admin.ModelAdmin):
    form = WebhookUrlAdminForm


# Register your models here.
admin.site.register(Match)
admin.site.register(VideoGoal)
admin.site.register(Team, TeamAdmin)
admin.site.register(TeamAlias, TeamAliasAdmin)
admin.site.register(AffiliateTerm)
admin.site.register(WebhookUrl, WebhookUrlAdmin)
