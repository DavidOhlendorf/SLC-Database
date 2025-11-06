from django.db import migrations

SQL_FORWARDS = """
-- tsvector-GIN Index für die Volltextsuche im Variablenlabel (deutscher Analyzer)
CREATE INDEX IF NOT EXISTS ix_v_varlab_tsv_gin
  ON variables_variable
  USING GIN (to_tsvector('german', coalesce(varlab, '')));
"""

SQL_BACKWARDS = """
DROP INDEX IF EXISTS ix_v_varlab_tsv_gin;
"""

class Migration(migrations.Migration):
    dependencies = [
        ("variables", "0004_trgm_gin_indices"), 
    ]

    operations = [
        migrations.RunSQL(SQL_FORWARDS, SQL_BACKWARDS),
    ]
