# pages/migrations/00xx_page_survey_integrity_triggers.py
from django.db import migrations


CREATE_SQL = r"""
-- Funktion 1: Mixed-survey verhindern + pagename pro survey unique erzwingen
CREATE OR REPLACE FUNCTION {fn_name}() RETURNS trigger AS $$
DECLARE
  new_survey_id integer;
  existing_survey_id integer;
  page_name text;
BEGIN
  -- Survey der neu verknüpften Wave ermitteln
  SELECT w.survey_id INTO new_survey_id
  FROM {wave_table} w
  WHERE w.id = NEW.wave_id;

  IF new_survey_id IS NULL THEN
    RAISE EXCEPTION 'Wave % hat keinen Survey; Page-Verknüpfung ist nicht erlaubt.', NEW.wave_id;
  END IF;

  -- (A) Prüfen: Page hängt bereits an Waves aus anderem Survey?
  SELECT w2.survey_id INTO existing_survey_id
  FROM {m2m_table} m
  JOIN {wave_table} w2 ON w2.id = m.wave_id
  WHERE m.wavepage_id = NEW.wavepage_id
  LIMIT 1;

  IF existing_survey_id IS NOT NULL AND existing_survey_id <> new_survey_id THEN
    RAISE EXCEPTION
      'WavePage % kann nicht mit Survey % verknüpft werden, weil sie bereits an Survey % hängt.',
      NEW.wavepage_id, new_survey_id, existing_survey_id;
  END IF;

  -- (B) pagename pro Survey eindeutig?
  SELECT p.pagename INTO page_name
  FROM {page_table} p
  WHERE p.id = NEW.wavepage_id;

  IF EXISTS (
    SELECT 1
    FROM {m2m_table} m2
    JOIN {page_table} p2 ON p2.id = m2.wavepage_id
    JOIN {wave_table} w3 ON w3.id = m2.wave_id
    WHERE w3.survey_id = new_survey_id
      AND p2.pagename = page_name
      AND p2.id <> NEW.wavepage_id
    LIMIT 1
  ) THEN
    RAISE EXCEPTION
      'Seitenname "%" existiert im Survey % bereits (WavePage %).',
      page_name, new_survey_id, NEW.wavepage_id;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger auf Through-Tabelle
DROP TRIGGER IF EXISTS {trigger_name} ON {m2m_table};
CREATE TRIGGER {trigger_name}
BEFORE INSERT OR UPDATE ON {m2m_table}
FOR EACH ROW
EXECUTE FUNCTION {fn_name}();
"""

DROP_SQL = r"""
DROP TRIGGER IF EXISTS {trigger_name} ON {m2m_table};
DROP FUNCTION IF EXISTS {fn_name}();
"""


def forwards(apps, schema_editor):
    Wave = apps.get_model("waves", "Wave")
    WavePage = apps.get_model("pages", "WavePage")

    m2m_table = WavePage.waves.through._meta.db_table
    wave_table = Wave._meta.db_table
    page_table = WavePage._meta.db_table

    fn_name = "pages_wavepage_waves_integrity_fn"
    trigger_name = "pages_wavepage_waves_integrity_trg"

    sql = CREATE_SQL.format(
        fn_name=fn_name,
        trigger_name=trigger_name,
        m2m_table=m2m_table,
        wave_table=wave_table,
        page_table=page_table,
    )

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(sql)


def backwards(apps, schema_editor):
    WavePage = apps.get_model("pages", "WavePage")
    m2m_table = WavePage.waves.through._meta.db_table

    fn_name = "pages_wavepage_waves_integrity_fn"
    trigger_name = "pages_wavepage_waves_integrity_trg"

    sql = DROP_SQL.format(
        fn_name=fn_name,
        trigger_name=trigger_name,
        m2m_table=m2m_table,
    )

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(sql)


class Migration(migrations.Migration):
    dependencies = [
        ("pages", "0008_wavepage_answer_validations_and_more"), 
        ("waves", "0016_wavequestion_uq_wavequestion_wave_question"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
