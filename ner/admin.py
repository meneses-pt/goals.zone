import json

from django import forms
from django.contrib import admin
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import F, Q
from django.http import HttpResponse
from rangefilter.filters import DateRangeFilter

from ner.models import NerLog


class TypeFilter(admin.SimpleListFilter):
    title = 'type'
    parameter_name = 'type'

    def lookups(self, request, model_admin):
        return (
            ('Correct', 'Correct'),
            ('Conflict', 'Conflict'),
            ('Failed Regex', 'Failed Regex'),
            ('Failed NER', 'Failed NER'),
            ('Not Identified', 'Not Identified'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        correct = queryset.filter(Q(regex_home_team=F('ner_home_team')) & Q(regex_away_team=F('ner_away_team')),
                                  regex_home_team__isnull=False,
                                  regex_away_team__isnull=False)
        conflict = queryset.filter(~Q(regex_home_team=F('ner_home_team')) | ~Q(regex_away_team=F('ner_away_team')),
                                   Q(regex_home_team__isnull=False) & ~Q(regex_home_team__exact=''),
                                   Q(regex_away_team__isnull=False) & ~Q(regex_away_team__exact=''),
                                   Q(ner_home_team__isnull=False) & ~Q(ner_home_team__exact=''),
                                   Q(ner_away_team__isnull=False) & ~Q(ner_away_team__exact=''))

        failed_regex = queryset.filter(((Q(regex_home_team__isnull=True) | Q(regex_away_team__isnull=True)
                                         | Q(regex_home_team__exact='') | Q(regex_away_team__exact=''))
                                        & Q(ner_home_team__isnull=False)
                                        & Q(ner_away_team__isnull=False)))
        failed_ner = queryset.filter(((Q(ner_home_team__isnull=True) | Q(ner_away_team__isnull=True)
                                       | Q(ner_home_team__exact='') | Q(ner_away_team__exact=''))
                                      & Q(regex_home_team__isnull=False)
                                      & Q(regex_away_team__isnull=False)))
        if value == 'Correct':
            return correct
        elif value == 'Conflict':
            return conflict
        elif value == 'Failed Regex':
            return failed_regex
        elif value == 'Failed NER':
            return failed_ner
        elif value == 'Not Identified':
            ids = queryset.difference(correct, conflict, failed_regex, failed_ner).values('id')
            return queryset.filter(id__in=ids)
        return queryset


class NerLogAdminForm(forms.ModelForm):
    class Meta:
        model = NerLog
        fields = ['title',
                  'regex_home_team',
                  'regex_away_team',
                  'ner_home_team',
                  'ner_away_team',
                  'reviewed']


def make_reviewed(modeladmin, request, queryset):
    queryset.update(reviewed=True)


make_reviewed.short_description = "Mark selected logs as reviewed"


def export_titles(self, request, queryset):
    titles = '\n'.join('{}'.format(item.title) for item in queryset.all())

    response = HttpResponse(titles, content_type='text/plain')
    response['Content-Disposition'] = 'attachment; filename=exported_titles.log'

    return response


export_titles.short_description = "Export titles"


class NerLogAdmin(admin.ModelAdmin):
    list_display = ['title',
                    'type',
                    'regex_home_team',
                    'regex_away_team',
                    'ner_home_team',
                    'ner_away_team',
                    'created_at',
                    'reviewed']
    list_filter = [('created_at', DateRangeFilter), 'reviewed', TypeFilter]
    actions = [make_reviewed, export_titles]
    form = NerLogAdminForm

    def changelist_view(self, request, extra_context=None):
        response = super(NerLogAdmin, self).changelist_view(request, extra_context)
        extra_context = {}
        if hasattr(response, 'context_data') and 'cl' in response.context_data:
            filtered_query_set = response.context_data["cl"].queryset
            qs = [o.type for o in filtered_query_set.all()]
            chart_data = {x: qs.count(x) for x in qs}

            # Serialize and attach the chart data to the template context
            as_json = json.dumps(chart_data, cls=DjangoJSONEncoder)
            extra_context = extra_context or {"chart_data": as_json}

        # Call the superclass changelist_view to render the page
        return super().changelist_view(request, extra_context=extra_context)


admin.site.register(NerLog, NerLogAdmin)
