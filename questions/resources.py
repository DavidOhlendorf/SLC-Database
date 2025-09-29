# questions/resources.py
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from .models import Question, WaveQuestion
from waves.models import Wave


class QuestionResource(resources.ModelResource):
    class Meta:
        model = Question
        fields = ('id', 'legacy_id', 'questiontext',)


class WaveQuestionResource(resources.ModelResource):
    wave = fields.Field(
        column_name='wave_legacy_id',
        attribute='wave',
        widget=ForeignKeyWidget(Wave, 'legacy_id')
    )
    question = fields.Field(
        column_name='question_legacy_id',
        attribute='question',
        widget=ForeignKeyWidget(Question, 'legacy_id')
    )

    class Meta:
        model = WaveQuestion
        fields = ('id', 'wave', 'question',)
