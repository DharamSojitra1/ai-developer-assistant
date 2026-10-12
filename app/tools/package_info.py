"""Live package metadata from the PyPI and npm registries.

Read-only calls to free public APIs, but the answer changes with every
release, so it is not deterministic. Only the two registry hosts can be
reached: every URL passes `validate_outbound_url` and redirects are never
followed.
"""

import asyncio
import re
from typing import Literal
from urllib.parse import quote

import httpx
from langchain_core.tools import tool
from pydantic import Field, model_validator

from app.config import REQUEST_TIMEOUT
from app.tools.schemas import NonBlankStr, StrictToolInput
from app.tools.tool_result import (
    handle_validation_error,
    tool_error,
    tool_success,
    with_timeout,
)
from app.utils.agent_logger import logger
from app.utils.url_safety import (
    UnsafeURLError,
    resolve_host,
    validate_outbound_url,
)

Ecosystem = Literal["pypi", "npm"]

REGISTRY_HOSTS = frozenset({"pypi.org", "registry.npmjs.org"})
MAX_PACKAGE_NAME_LENGTH = 214
MAX_FIELD_CHARS = 300

PACKAGE_NAME_PATTERNS: dict[str, re.Pattern] = {
    # PEP 508 project names.
    "pypi": re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$"),
    # npm names: lowercase, optionally scoped (@scope/name).
    "npm": re.compile(r"^(?:@[a-z0-9][a-z0-9._~-]*/)?[a-z0-9][a-z0-9._~-]*$"),
}

http_transport: httpx.AsyncBaseTransport | None = None


class PackageInfoInput(StrictToolInput):
    ecosystem: Ecosystem = Field(
        ...,
        description="'pypi' for Python packages, 'npm' for JavaScript ones.",
    )
    name: NonBlankStr = Field(
        ...,
        max_length=MAX_PACKAGE_NAME_LENGTH,
        description="Exact package name, e.g. 'fastapi' or '@types/react'.",
    )

    @model_validator(mode="after")
    def _check_name(self) -> "PackageInfoInput":
        if not PACKAGE_NAME_PATTERNS[self.ecosystem].fullmatch(self.name):
            raise ValueError(f"'{self.name}' is not a valid {self.ecosystem} package name")
        return self


class PackageNotFoundError(Exception):
    pass


class RegistryError(Exception):
    pass


def registry_url(ecosystem: str, name: str) -> str:
    if ecosystem == "pypi":
        return f"https://pypi.org/pypi/{quote(name, safe='')}/json"

    return f"https://registry.npmjs.org/{quote(name, safe='@')}/latest"


def _clip(value) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None

    value = value.strip()
    return value if len(value) <= MAX_FIELD_CHARS else value[: MAX_FIELD_CHARS - 1] + "…"


def parse_pypi(data: dict) -> dict:
    info = data.get("info") or {}
    files = data.get("urls") or []
    project_urls = info.get("project_urls") or {}

    return {
        "ecosystem": "pypi",
        "name": info.get("name"),
        "latest_version": info.get("version"),
        "released_at": files[0].get("upload_time_iso_8601") if files else None,
        "summary": _clip(info.get("summary")),
        "homepage": _clip(
            project_urls.get("Homepage")
            or project_urls.get("homepage")
            or info.get("home_page")
        ),
        "license": _clip(info.get("license_expression") or info.get("license")),
        "requires_python": info.get("requires_python"),
        "registry_url": f"https://pypi.org/project/{info.get('name')}/",
    }


def parse_npm(data: dict) -> dict:
    license_value = data.get("license")

    if isinstance(license_value, dict):
        license_value = license_value.get("type")

    return {
        "ecosystem": "npm",
        "name": data.get("name"),
        "latest_version": data.get("version"),
        # The /latest manifest has no publish date; the full document that
        # does can be tens of megabytes for popular packages.
        "released_at": None,
        "summary": _clip(data.get("description")),
        "homepage": _clip(data.get("homepage")),
        "license": _clip(license_value),
        "requires_node": (data.get("engines") or {}).get("node"),
        "registry_url": f"https://www.npmjs.com/package/{data.get('name')}",
    }


async def fetch_package(ecosystem: str, name: str) -> dict:
    url = registry_url(ecosystem, name)
    await asyncio.to_thread(
        validate_outbound_url, url, REGISTRY_HOSTS, resolve_host
    )

    try:
        async with httpx.AsyncClient(
            transport=http_transport,
            timeout=REQUEST_TIMEOUT,
            follow_redirects=False,
        ) as client:
            response = await client.get(
                url, headers={"Accept": "application/json"}
            )
    except httpx.HTTPError as exc:
        raise RegistryError(f"{ecosystem} request failed: {exc!r}") from exc

    if response.status_code == 404:
        raise PackageNotFoundError(name)

    if response.status_code != 200:
        raise RegistryError(f"{ecosystem} returned HTTP {response.status_code}")

    try:
        data = response.json()
    except ValueError as exc:
        raise RegistryError(f"{ecosystem} returned invalid JSON") from exc

    if not isinstance(data, dict):
        raise RegistryError(f"{ecosystem} returned an unexpected payload")

    return parse_pypi(data) if ecosystem == "pypi" else parse_npm(data)


@tool(args_schema=PackageInfoInput)
@with_timeout("The package registry did not respond in time. Try again later.")
async def package_info(ecosystem: Ecosystem, name: str) -> str:
    """
    Look up live metadata for a PyPI or npm package: the latest released
    version, release date (PyPI only), summary, homepage, and license.

    Use this whenever the user asks about the latest or current version of
    a package, or whether a package exists; never guess versions.
    """
    try:
        return tool_success(await fetch_package(ecosystem, name))
    except PackageNotFoundError:
        return tool_error(f"No {ecosystem} package named '{name}' was found.")
    except UnsafeURLError:
        logger.exception("Package registry URL was rejected")
        return tool_error("The package registry could not be reached safely.")
    except RegistryError:
        logger.exception("Package registry lookup failed")
        return tool_error("The package registry lookup failed. Try again later.")


package_info.handle_validation_error = handle_validation_error
