import re
import unicodedata

MAX_TRANSCRIPT_LENGTH = 180


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    return "".join(
        character for character in normalized if unicodedata.category(character) != "Mn"
    ).lower()


def create_assistant_reply(transcript: str) -> str:
    clean_transcript = re.sub(r"\s+", " ", transcript).strip()
    normalized_transcript = normalize_text(clean_transcript)

    if re.search(r"\b(oi|ola|bom dia|boa tarde|boa noite)\b", normalized_transcript):
        return "Olá! Que bom falar com você. Como posso ajudar?"

    if re.search(r"\b(ajuda|o que voce faz|como funciona)\b", normalized_transcript):
        return (
            "Posso abrir sites, aplicativos e pastas, fazer pesquisas, controlar "
            "volume e mídia, além de responder data e hora."
        )

    if re.search(r"\b(obrigado|obrigada|valeu)\b", normalized_transcript):
        return "Por nada! Estou à disposição."

    safe_transcript = clean_transcript[:MAX_TRANSCRIPT_LENGTH]
    return (
        f"Ouvi: {safe_transcript}. "
        "Ainda não tenho uma ação registrada para esse pedido."
    )
