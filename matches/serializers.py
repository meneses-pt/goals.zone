from rest_framework import serializers

from matches.models import Match, Team, VideoGoal, VideoGoalMirror


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ["name", "logo_file", "slug"]


class VideoGoalMirrorSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoGoalMirror
        fields = ["title", "url"]


class VideoGoalSerializer(serializers.ModelSerializer):
    reddit_link = serializers.CharField()
    mirrors = VideoGoalMirrorSerializer(many=True, read_only=True, source="calculated_mirrors")

    class Meta:
        model = VideoGoal
        fields = ["title", "reddit_link", "mirrors"]


class MatchSerializer(serializers.ModelSerializer):
    home_team = TeamSerializer(many=False, read_only=True)
    away_team = TeamSerializer(many=False, read_only=True)

    class Meta:
        model = Match
        fields = [
            "id",
            "home_team",
            "away_team",
            "score",
            "home_team_score",
            "away_team_score",
            "datetime",
            "slug",
        ]


class MatchDetailSerializer(serializers.ModelSerializer):
    home_team = TeamSerializer(many=False, read_only=True)
    away_team = TeamSerializer(many=False, read_only=True)
    videos = VideoGoalSerializer(many=True, read_only=True, source="videogoal_set")

    class Meta:
        model = Match
        fields = [
            "id",
            "home_team",
            "away_team",
            "score",
            "home_team_score",
            "away_team_score",
            "datetime",
            "slug",
            "videos",
        ]
