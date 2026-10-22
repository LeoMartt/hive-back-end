from django.db import migrations
from django.utils import timezone
from django.utils.dateparse import parse_datetime


def preserve_history(apps, schema_editor):
    Activity = apps.get_model("activities", "Activity")
    Event = apps.get_model("activities", "ActivityStatusEvent")
    using = schema_editor.connection.alias
    for activity in Activity.objects.using(using).all().iterator():
        events = [Event(atividade_id=activity.pk, ocorrido_em=activity.criado_em,
            texto="Atividade criada", status_novo="", origem="legado", atividade_nome=activity.nome,
            autor_nome="Autor não registrado no sistema anterior")]
        for row in activity.historico_status or []:
            if not isinstance(row, dict):
                continue
            at = parse_datetime(str(row.get("at", "")))
            if at is not None and timezone.is_naive(at):
                at = timezone.make_aware(at)
            events.append(Event(atividade_id=activity.pk, ocorrido_em=at or timezone.now(),
                texto=str(row.get("text", "Registro legado")), origem="legado", atividade_nome=activity.nome,
                autor_nome="Autor não registrado no sistema anterior",
                motivo="" if at else "Data original ausente ou inválida; registrada a data da migração"))
        texts = [str(row.get("text", "")) for row in activity.historico_status or [] if isinstance(row, dict)]
        blocks = sum(text.endswith("→ Bloqueado") for text in texts)
        releases = sum(text == "Bloqueado → Liberado" for text in texts)
        # Reconcile only when the captured blocking cycles explain the old counter.
        if blocks == activity.numero_retest and releases != activity.numero_retest and activity.issues.exists():
            Activity.objects.using(using).filter(pk=activity.pk).update(numero_retest=releases)
            events.append(Event(atividade_id=activity.pk, ocorrido_em=timezone.now(),
                texto=f"Contador de retestes corrigido: {activity.numero_retest} → {releases}",
                origem="migracao_reteste", atividade_nome=activity.nome, autor_nome="Sistema / migração",
                motivo="Nova regra: contar somente Bloqueado → Liberado em atividade com issue"))
        Event.objects.using(using).bulk_create(events)


def protect_history(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute("""
            CREATE FUNCTION hive_reject_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'Activity audit events are append-only'; END;
            $$;
            CREATE TRIGGER hive_activity_audit_immutable BEFORE UPDATE OR DELETE OR TRUNCATE
            ON activities_activitystatusevent FOR EACH STATEMENT EXECUTE FUNCTION hive_reject_audit_mutation();
            CREATE FUNCTION hive_freeze_legacy_history() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF NEW.historico_status IS DISTINCT FROM OLD.historico_status THEN
                    RAISE EXCEPTION 'Legacy activity history is immutable';
                END IF;
                RETURN NEW;
            END;
            $$;
            CREATE TRIGGER hive_activity_legacy_immutable BEFORE UPDATE OF historico_status
            ON activities_activity FOR EACH ROW EXECUTE FUNCTION hive_freeze_legacy_history();
        """)
    elif vendor == "sqlite":
        for operation in ("UPDATE", "DELETE"):
            schema_editor.execute(f"""CREATE TRIGGER hive_activity_audit_no_{operation.lower()}
                BEFORE {operation} ON activities_activitystatusevent BEGIN
                SELECT RAISE(ABORT, 'Activity audit events are append-only'); END""")
        schema_editor.execute("""CREATE TRIGGER hive_activity_legacy_immutable
            BEFORE UPDATE OF historico_status ON activities_activity
            WHEN NEW.historico_status IS NOT OLD.historico_status
            BEGIN SELECT RAISE(ABORT, 'Legacy activity history is immutable'); END""")
    else:
        raise RuntimeError("Audit immutability requires PostgreSQL or SQLite")


def unprotect_history(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("""
            DROP TRIGGER IF EXISTS hive_activity_audit_immutable ON activities_activitystatusevent;
            DROP TRIGGER IF EXISTS hive_activity_legacy_immutable ON activities_activity;
            DROP FUNCTION IF EXISTS hive_reject_audit_mutation();
            DROP FUNCTION IF EXISTS hive_freeze_legacy_history();
        """)
    elif schema_editor.connection.vendor == "sqlite":
        for name in ("hive_activity_audit_no_update", "hive_activity_audit_no_delete", "hive_activity_legacy_immutable"):
            schema_editor.execute(f"DROP TRIGGER IF EXISTS {name}")


class Migration(migrations.Migration):
    dependencies = [("activities", "0007_activitystatusevent"), ("issues", "0001_initial")]
    operations = [migrations.RunPython(preserve_history, migrations.RunPython.noop),
        migrations.RunPython(protect_history, unprotect_history)]
