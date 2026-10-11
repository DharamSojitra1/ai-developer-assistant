from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict


def _reject_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be blank")

    return value


NonBlankStr = Annotated[str, AfterValidator(_reject_blank)]


class StrictToolInput(BaseModel):
    """Base for tool argument schemas.

    Unknown arguments are rejected rather than silently dropped, and
    values are not coerced (e.g. 123 is not accepted as a string).
    """

    model_config = ConfigDict(extra="forbid", strict=True)
