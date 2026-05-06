import re
import uuid


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9\s-]", "", value).strip().lower()
    return re.sub(r"[\s_-]+", "-", value)


def generate_verification_token() -> str:
    return uuid.uuid4().hex[:24]
