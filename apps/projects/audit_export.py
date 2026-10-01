import re
import unicodedata
from datetime import date, datetime
from html import escape
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.activities.models import Activity
from apps.accounts.models import Usuario

from .models import Project


TEMPLATE_PATH = settings.BASE_DIR / "docs" / "templates" / "auditoria_atividade_template.docx"
EVIDENCE_URL_PLACEHOLDER = "{{activity.evidencia.url}}"


def _safe_name(value: str, *, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", ascii_text).strip("._-")
    return cleaned[:90] or fallback


def _evidence_link(evidence: dict | None) -> str:
    if not evidence:
        return "Sem evidencia"
    return evidence.get("url") or evidence.get("storagePath") or "evidencia sem link"


def _format_date(value) -> str:
    if value is None:
        return "Nao informado"
    if isinstance(value, datetime):
        return timezone.localtime(value).strftime("%d/%m/%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return str(value)


def _user_name(user: Usuario | None) -> str:
    if user is None:
        return "Nao informado"
    return user.first_name or user.username or user.email


def _evidence_value(evidence: dict | None, key: str) -> str:
    if not evidence:
        return "Sem evidencia"
    return evidence.get(key) or "Nao informado"


def _evidence_datetime_value(evidence: dict | None, key: str) -> str:
    if not evidence:
        return "Sem evidencia"

    value = evidence.get(key)
    if not value:
        return "Nao informado"

    if isinstance(value, datetime):
        return _format_date(value)

    if isinstance(value, str):
        parsed = parse_datetime(value)
        if parsed is not None:
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
            return _format_date(parsed)

    return str(value)


def _join(values: list[str], empty: str = "Nenhum") -> str:
    cleaned = [value for value in values if value]
    return "; ".join(cleaned) if cleaned else empty


def _activity_module(activity: Activity) -> str:
    if activity.no.nivel == 1:
        return activity.no.nome
    return activity.no.parent.nome if activity.no.parent else "Nao informado"


def _activity_process(activity: Activity) -> str:
    if activity.no.nivel == 1:
        return "Nao se aplica"
    return activity.no.nome


def _context(project: Project, activity: Activity) -> dict[str, str]:
    activity_evidence = activity.evidencia_aprovacao

    return {
        "{{project.codigo}}": _safe_name(project.nome, fallback=str(project.id)),
        "{{project.id}}": str(project.id),
        "{{project.nome}}": project.nome,
        "{{project.modo}}": project.get_modo_display(),
        "{{project.gestor_nome}}": _user_name(project.criado_por),
        "{{project.gestor_email}}": project.criado_por.email if project.criado_por_id else "Nao informado",
        "{{activity.codigo}}": activity.codigo_visivel,
        "{{activity.nome}}": activity.nome,
        "{{activity.nome_sanitizado}}": _safe_name(activity.nome, fallback="atividade"),
        "{{activity.status}}": activity.get_status_display(),
        "{{activity.modulo}}": _activity_module(activity),
        "{{activity.processo}}": _activity_process(activity),
        "{{activity.sistema}}": activity.sistema or "Nao informado",
        "{{activity.area}}": activity.area or "Nao informado",
        "{{activity.transacao}}": activity.transacao or "Nao informado",
        "{{activity.resultado_esperado}}": activity.resultado_esperado or "Nao informado",
        "{{activity.observacoes}}": activity.observacoes or "Nao informado",
        "{{activity.observacao_aprovacao}}": activity.observacao_aprovacao or "Nao informado",
        "{{activity.conclusao_observacao}}": activity.observacao_aprovacao or "Nao informado",
        "{{activity.inicio_observacao}}": activity.observacoes or "Nao informado",
        "{{activity.numero_retest}}": str(activity.numero_retest),
        "{{activity.tester_nome}}": _user_name(activity.tester),
        "{{activity.tester_email}}": activity.tester.email,
        "{{activity.dev_nome}}": _user_name(activity.desenvolvedor),
        "{{activity.dev_email}}": activity.desenvolvedor.email,
        "{{activity.data_inicio_planejada}}": _format_date(activity.data_inicio_planejada),
        "{{activity.data_conclusao_planejada}}": _format_date(activity.data_conclusao_planejada),
        "{{activity.data_inicio_real}}": _format_date(activity.data_inicio_real),
        "{{activity.data_conclusao_real}}": _format_date(activity.data_conclusao_real),
        "{{activity.predecessoras}}": _join([item.codigo_visivel for item in activity.predecessoras.all()]),
        "{{activity.evidencia.file_name}}": _evidence_value(activity_evidence, "fileName"),
        "{{activity.evidencia.uploaded_by}}": _evidence_value(activity_evidence, "uploadedBy"),
        "{{activity.evidencia.uploaded_at}}": _evidence_value(activity_evidence, "uploadedAt"),
        "{{activity.evidencia.storage_path}}": _evidence_value(activity_evidence, "storagePath"),
        "{{activity.evidencia.url}}": _evidence_link(activity_evidence),
        "{{activity.evidencia.expires_at}}": _evidence_datetime_value(activity_evidence, "urlExpiresAt"),
        "{{storage.project_prefix}}": f"projects/{project.id}/activities/{activity.codigo_visivel}",
    }


def _is_http_url(value: str) -> bool:
    return value.startswith("https://") or value.startswith("http://")


def _next_relationship_id(rels_xml: str) -> str:
    ids = [int(match) for match in re.findall(r'\bId="rId(\d+)"', rels_xml)]
    return f"rId{max(ids, default=0) + 1}"


def _add_hyperlink_relationship(rels_xml: str, relationship_id: str, url: str) -> str:
    relationship = (
        f'<Relationship Id="{relationship_id}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
        f'Target="{escape(url, quote=True)}" TargetMode="External"/>'
    )
    return rels_xml.replace("</Relationships>", f"{relationship}</Relationships>")


def _hyperlink_xml(relationship_id: str, label: str) -> str:
    escaped_label = escape(label)
    return (
        f'<w:hyperlink r:id="{relationship_id}" w:history="1">'
        "<w:r>"
        "<w:rPr><w:rStyle w:val=\"Hyperlink\"/></w:rPr>"
        f"<w:t>{escaped_label}</w:t>"
        "</w:r>"
        "</w:hyperlink>"
    )


def _replace_placeholder_run_with_hyperlink(document_xml: str, relationship_id: str, url: str) -> str:
    hyperlink = _hyperlink_xml(relationship_id, url)
    pattern = re.compile(
        r"<w:r(?:\s[^>]*)?>(?:(?!</w:r>).)*?<w:t(?:\s[^>]*)?>"
        + re.escape(EVIDENCE_URL_PLACEHOLDER)
        + r"</w:t>(?:(?!</w:r>).)*?</w:r>",
        re.DOTALL,
    )
    replaced, count = pattern.subn(hyperlink, document_xml, count=1)
    if count:
        return replaced
    return document_xml.replace(EVIDENCE_URL_PLACEHOLDER, escape(url))


def _render_docx(template_bytes: bytes, replacements: dict[str, str]) -> bytes:
    output = BytesIO()
    with ZipFile(BytesIO(template_bytes), "r") as source, ZipFile(output, "w", ZIP_DEFLATED) as target:
        files = {item.filename: source.read(item.filename) for item in source.infolist()}
        hyperlink_url = replacements.get(EVIDENCE_URL_PLACEHOLDER, "")
        hyperlink_relationship_id = None

        if _is_http_url(hyperlink_url):
            rels_path = "word/_rels/document.xml.rels"
            rels_xml = files[rels_path].decode("utf-8")
            hyperlink_relationship_id = _next_relationship_id(rels_xml)
            files[rels_path] = _add_hyperlink_relationship(
                rels_xml,
                hyperlink_relationship_id,
                hyperlink_url,
            ).encode("utf-8")

        for item in source.infolist():
            data = files[item.filename]
            if item.filename.startswith("word/") and item.filename.endswith(".xml"):
                text = data.decode("utf-8")
                if item.filename == "word/document.xml" and hyperlink_relationship_id:
                    text = _replace_placeholder_run_with_hyperlink(
                        text,
                        hyperlink_relationship_id,
                        hyperlink_url,
                    )
                for placeholder, value in replacements.items():
                    if placeholder == EVIDENCE_URL_PLACEHOLDER and hyperlink_relationship_id:
                        continue
                    text = text.replace(placeholder, escape(value))
                data = text.encode("utf-8")
            target.writestr(item, data)
    return output.getvalue()


def gerar_zip_auditoria_projeto(project: Project, *, generated_by: Usuario | None = None) -> bytes:
    template_bytes = Path(TEMPLATE_PATH).read_bytes()
    output = BytesIO()
    project_dir = _safe_name(project.nome, fallback=f"projeto_{project.id}")

    activities = (
        Activity.objects.filter(projeto=project)
        .select_related("no", "tester", "desenvolvedor")
        .prefetch_related("predecessoras")
        .order_by("id")
    )

    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for activity in activities:
            activity_dir = f"{project_dir}/{activity.codigo_visivel}_{_safe_name(activity.nome, fallback='atividade')}"
            docx_name = f"{activity.codigo_visivel}_{_safe_name(activity.nome, fallback='atividade')}.docx"
            docx_bytes = _render_docx(template_bytes, _context(project, activity))
            archive.writestr(f"{activity_dir}/{docx_name}", docx_bytes)

    return output.getvalue()
