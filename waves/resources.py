from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from waves.models import Wave, WaveQuestion
from questions.models import Question


class WaveResource(resources.ModelResource):
    class Meta:
        model = Wave
        fields = ('id','legacy_id','surveyyear','cycle','instrument','start_date','end_date','is_locked',)


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
    legacy_screenshot_id = fields.Field(
        column_name='screenshotID',
        attribute='legacy_screenshot_id'
    )

    class Meta:
        model = WaveQuestion
        fields = ('id', 'wave', 'question', 'legacy_screenshot_id',)



