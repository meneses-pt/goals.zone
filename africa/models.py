from django.db import models

from matches.models import Match, Tournament, Category, Team


class AfricaMatch(models.Model):
    match = models.OneToOneField(Match, related_name='africa_match', on_delete=models.PROTECT)

    class Meta:
        db_table = 'africa_match'


class AfricaMatchesFilter(models.Model):
    include_tournaments = models.ManyToManyField(Tournament,
                                                 related_name='%(class)s_include_tournaments',
                                                 default=None,
                                                 blank=True)
    include_categories = models.ManyToManyField(Category,
                                                related_name='%(class)s_include_categories',
                                                default=None,
                                                blank=True)
    exclude_tournaments = models.ManyToManyField(Tournament,
                                                 related_name='%(class)s_exclude_tournaments',
                                                 default=None,
                                                 blank=True)
    exclude_categories = models.ManyToManyField(Category,
                                                related_name='%(class)s_exclude_categories',
                                                default=None,
                                                blank=True)

    @classmethod
    def object(cls):
        return cls._default_manager.all().first()

    def save(self, *args, **kwargs):
        self.pk = self.id = 1
        return super().save(*args, **kwargs)
