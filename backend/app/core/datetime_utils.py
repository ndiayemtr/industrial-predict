from datetime import datetime


def validate_timezone(
    value: datetime | None,
    *,
    field_name: str,
) -> datetime | None:
    if value is None:
        return None

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            f"{field_name} must include timezone information"
        )

    return value