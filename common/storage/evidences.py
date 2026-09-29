from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    ContentSettings,
    generate_blob_sas,
)
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from common.validators.attachments import validar_anexo_evidencia


def _settings_value(name: str) -> str:
    value = getattr(settings, name, "")
    if not value:
        raise ValidationError({"storage": f"Configuração {name} não foi definida."})
    return value


def _blob_service_client() -> BlobServiceClient:
    account_name = _settings_value("AZURE_ACCOUNT_NAME")
    account_key = _settings_value("AZURE_ACCOUNT_KEY")
    return BlobServiceClient(
        account_url=f"https://{account_name}.blob.core.windows.net",
        credential=account_key,
    )


def _safe_filename(filename: str) -> str:
    stem = Path(filename).stem.lower()
    suffix = Path(filename).suffix.lower()
    safe_stem = "".join(char if char.isalnum() else "-" for char in stem).strip("-")
    safe_stem = "-".join(part for part in safe_stem.split("-") if part)
    if not safe_stem:
        safe_stem = "evidencia"
    return f"{safe_stem[:80]}{suffix}"


def _size_label(size_bytes: int) -> str:
    return f"{max(1, (size_bytes + 1023) // 1024)} KB"


def _public_blob_url(account_name: str, container: str, blob_name: str) -> str:
    return f"https://{account_name}.blob.core.windows.net/{container}/{blob_name}"


def _sas_url(*, account_name: str, account_key: str, container: str, blob_name: str, expires_at) -> str:
    token = generate_blob_sas(
        account_name=account_name,
        container_name=container,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=expires_at,
    )
    return f"{_public_blob_url(account_name, container, blob_name)}?{token}"


def upload_evidencia(*, uploaded_file, blob_prefix: str, uploaded_by: str) -> dict:
    if uploaded_file is None:
        return None

    base_metadata = validar_anexo_evidencia(
        {
            "fileName": uploaded_file.name,
            "sizeLabel": _size_label(uploaded_file.size),
            "uploadedBy": uploaded_by,
            "uploadedAt": timezone.now().isoformat(),
            "contentType": getattr(uploaded_file, "content_type", "") or "",
        },
        field_name="evidenceFile",
    )

    account_name = _settings_value("AZURE_ACCOUNT_NAME")
    account_key = _settings_value("AZURE_ACCOUNT_KEY")
    container = _settings_value("AZURE_CONTAINER")
    expires_at = timezone.now() + timedelta(days=getattr(settings, "AZURE_EVIDENCE_SAS_DAYS", 180))

    safe_filename = _safe_filename(uploaded_file.name)
    blob_name = f"{blob_prefix.strip('/')}/{uuid4().hex}-{safe_filename}"
    content_type = base_metadata.get("contentType") or "application/octet-stream"

    client = _blob_service_client()
    blob_client = client.get_blob_client(container=container, blob=blob_name)
    uploaded_file.seek(0)
    blob_client.upload_blob(
        uploaded_file,
        overwrite=False,
        content_settings=ContentSettings(content_type=content_type),
    )

    return {
        **base_metadata,
        "storagePath": blob_name,
        "url": _sas_url(
            account_name=account_name,
            account_key=account_key,
            container=container,
            blob_name=blob_name,
            expires_at=expires_at,
        ),
        "urlExpiresAt": expires_at.isoformat(),
    }
