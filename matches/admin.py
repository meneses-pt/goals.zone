from django.contrib import admin

from .models import AffiliateTerm, Category, Match, Season, Team, TeamAlias, Tournament, VideoGoal


class VideoGoalAdmin(admin.ModelAdmin):
    autocomplete_fields = ["match"]


class MatchAdmin(admin.ModelAdmin):
    search_fields = ["home_team__name", "away_team__name", "tournament", "category", "season"]
    autocomplete_fields = ["home_team", "away_team"]


class TeamAdmin(admin.ModelAdmin):
    search_fields = ["name"]


class TeamAliasAdmin(admin.ModelAdmin):
    autocomplete_fields = ["team"]
    search_fields = ["alias", "team__name"]


class TournamentAdmin(admin.ModelAdmin):
    search_fields = ["name"]


class CategoryAdmin(admin.ModelAdmin):
    search_fields = ["name"]


class SeasonAdmin(admin.ModelAdmin):
    search_fields = ["name"]


# Register your models here.
admin.site.register(Tournament, TournamentAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Season, SeasonAdmin)
admin.site.register(Match, MatchAdmin)
admin.site.register(VideoGoal, VideoGoalAdmin)
admin.site.register(Team, TeamAdmin)
admin.site.register(TeamAlias, TeamAliasAdmin)
admin.site.register(AffiliateTerm)
