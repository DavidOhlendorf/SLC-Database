from django.db import migrations

SQL_FORWARDS = """
CREATE INDEX IF NOT EXISTS ix_variable_varlab_trgm
  ON variables_variable
  USING gin (lower(varlab) gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_variable_varname_btree
  ON variables_variable
  (lower(varname) varchar_pattern_ops);
"""

SQL_BACKWARDS = """
DROP INDEX IF EXISTS ix_variable_varlab_trgm;
DROP INDEX IF EXISTS ix_variable_varname_btree;
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
        ("variables", "0003_alter_variable_varlab"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
