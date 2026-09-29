from pathlib import Path

from rest_framework.exceptions import ValidationError


AUDIO_EXTENSIONS = {
    ".aac",
    ".flac",
    ".m4a",
    ".mp3",
    ".ogg",
    ".wav",
    ".wma",
}

VIDEO_EXTENSIONS = {
    ".avi",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".webm",
    ".wmv",
}


def validar_anexo_evidencia(anexo, *, field_name: str):
    if not anexo:
        return None

    if not isinstance(anexo, dict):
        raise ValidationError({field_name: "Evidência deve ser um objeto com metadados do arquivo."})

    file_name = str(anexo.get("fileName") or "").strip()
    if not file_name:
        raise ValidationError({field_name: "Nome do arquivo da evidência é obrigatório."})

    content_type = str(anexo.get("contentType") or "").strip().lower()
    extension = Path(file_name).suffix.lower()

    if content_type.startswith("audio/") or content_type.startswith("video/"):
        raise ValidationError({field_name: "Evidências em áudio ou vídeo não são permitidas."})

    if extension in AUDIO_EXTENSIONS or extension in VIDEO_EXTENSIONS:
        raise ValidationError({field_name: "Evidências em áudio ou vídeo não são permitidas."})

    return anexo
