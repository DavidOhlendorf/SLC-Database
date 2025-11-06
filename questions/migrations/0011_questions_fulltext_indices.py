from django.db import migrations

SQL_FORWARDS = """
-- tsvector-GIN Index für die Volltextsuche (deutscher Analyzer)
CREATE INDEX IF NOT EXISTS ix_q_text_tsv_gin
  ON questions_question
  USING GIN (to_tsvector('german', coalesce(questiontext, '')));
"""

SQL_BACKWARDS = """
DROP INDEX IF EXISTS ix_q_text_tsv_gin;
"""

class Migration(migrations.Migration):
    dependencies = [
        ("questions", "0010_trgm_gin_indices"),
    ]
    operations = [
        migrations.RunSQL(SQL_FORWARDS, SQL_BACKWARDS),
    ]
