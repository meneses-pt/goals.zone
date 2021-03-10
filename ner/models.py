from django.db import models
from django.forms import model_to_dict


class NerLog(models.Model):
    title = models.CharField(max_length=1024, unique=True)
    regex_home_team = models.CharField(max_length=256, default=None, null=True, blank=True)
    regex_away_team = models.CharField(max_length=256, default=None, null=True, blank=True)
    ner_home_team = models.CharField(max_length=256, default=None, null=True, blank=True)
    ner_away_team = models.CharField(max_length=256, default=None, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed = models.BooleanField(default=False)

    @property
    def type(self):
        if self.regex_home_team and \
                self.regex_away_team and \
                self.ner_home_team and \
                self.ner_away_team and \
                self.regex_home_team == self.ner_home_team and \
                self.regex_away_team == self.ner_away_team:
            return 'Correct'
        if self.regex_home_team and \
                self.regex_away_team and \
                self.ner_home_team and \
                self.ner_away_team and \
                (self.regex_home_team != self.ner_home_team or
                 self.regex_away_team != self.ner_away_team):
            return 'Conflict'
        if (not self.regex_home_team or
            not self.regex_away_team) and \
                self.ner_home_team and \
                self.ner_away_team:
            return 'Failed Regex'
        if (not self.ner_home_team or
            not self.ner_away_team) and \
                self.regex_home_team and \
                self.regex_away_team:
            return 'Failed NER'
        return 'Not Identified'

    # noinspection PyPep8Naming
    def toJSON(self):
        return {
            **model_to_dict(self, fields=['title', 'regex_home_team', 'regex_away_team', 'ner_home_team', 'ner_away_team', 'created_at', 'reviewed']),
            **{'type': self.type}
        }

    def __str__(self):
        return str(self.title)
