from django.db import migrations

SQL_FORWARDS = """
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS ix_q_text_trgm
  ON questions_question
  USING gin (lower(questiontext) gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_keyword_name_trgm
  ON questions_keyword
  USING gin (lower(name) gin_trgm_ops);
"""

SQL_BACKWARDS = """
DROP INDEX IF EXISTS ix_q_text_trgm;
DROP INDEX IF EXISTS ix_keyword_name_trgm;
"""

def forwards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cur:
            cur.execute(SQL_FORWARDS)

def backwards(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as cur:
            cur.execute(SQL_BACKWARDS)

class Migration(migrations.Migration):

    dependencies = [
        ("questions", "0009_questionscreenshot_legacy_id"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
