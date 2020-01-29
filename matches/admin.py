from django.contrib import admin

from .models import Match, VideoGoal, Team, TeamAlias, AffiliateTerm


class TeamAdmin(admin.ModelAdmin):
    search_fields = ['name']


class TeamAliasAdmin(admin.ModelAdmin):
    autocomplete_fields = ['team']
    search_fields = ['team']
    raw_id_fields = ['team']


# Register your models here.
admin.site.register(Match)
admin.site.register(VideoGoal)
admin.site.register(Team, TeamAdmin)
admin.site.register(TeamAlias, TeamAliasAdmin)
admin.site.register(AffiliateTerm)
