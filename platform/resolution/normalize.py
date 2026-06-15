import re
import unicodedata

_CHAR_MAP = {
    ord("ø"): "o", ord("Ø"): "o",
    ord("æ"): "ae", ord("Æ"): "ae",
    ord("ß"): "ss",
    ord("œ"): "oe", ord("Œ"): "oe",
    ord("ʼ"): "", ord("'"): "", ord("'"): "",
    ord("·"): "",
}


def normalize(name: str) -> str:
    """Canonical form used for fuzzy matching and dedup: lowercase ASCII, spaces collapsed."""
    name = name.translate(_CHAR_MAP)
    decomposed = unicodedata.normalize("NFKD", name.lower())
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", ascii_only).strip()
