from django_hosts import host, patterns

host_patterns = patterns(
    "",
    host(r"goals.zone", "goals_zone.urls", name="goals_zone"),
    host(r"goals.africa", "africa.urls", name="africa"),
)
