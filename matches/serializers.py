from rest_framework import serializers

from matches.models import Match, Team


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ["name", "logo_file", "slug"]


class MatchSerializer(serializers.ModelSerializer):
    home_team = TeamSerializer(many=False, read_only=True)
    away_team = TeamSerializer(many=False, read_only=True)

    class Meta:
        model = Match
        fields = [
            "home_team",
            "away_team",
            "score",
            "home_team_score",
            "away_team_score",
            "datetime",
            "slug",
        ]
