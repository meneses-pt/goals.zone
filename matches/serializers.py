from django.db.models import Count, Q
from rest_framework import pagination, serializers

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
    simple_permalink = serializers.CharField()
    mirrors = VideoGoalMirrorSerializer(many=True, read_only=True, source="calculated_mirrors")

    class Meta:
        model = VideoGoal
        fields = ["title", "reddit_link", "mirrors", "simple_permalink"]


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


class TeamDetailSerializer(serializers.ModelSerializer):
    matches = serializers.SerializerMethodField("paginated_matches")

    class Meta:
        model = Team
        paginate_by = 25
        fields = ["name", "logo_file", "slug", "matches"]

    def paginated_matches(self, obj):
        team_matches = (
            Match.objects.annotate(vg_count=Count("videogoal"))
            .filter(Q(home_team=obj) | Q(away_team=obj))
            .filter(vg_count__gt=0)
            .order_by("-datetime")
        )
        paginator = pagination.LimitOffsetPagination()
        page = paginator.paginate_queryset(team_matches, self.context["request"])
        serializer = MatchSerializer(page, many=True, context={"request": self.context["request"]})
        return serializer.data


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
