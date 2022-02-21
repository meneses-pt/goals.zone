from django_hosts import patterns, host

from goals_zone import settings

host_patterns = patterns(
    '',
    host(r'goals.zone', 'goals_zone.urls', name='goals_zone'),
    host(r'goals.africa', 'africa.urls', name='africa'),
)
