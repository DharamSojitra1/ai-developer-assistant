import json

import httpx
import pytest

from app.tools import package_info as package_info_module
from app.tools.package_info import package_info, registry_url
from app.utils.url_safety import UnsafeURLError, validate_outbound_url

PYPI_FASTAPI = {
    "info": {
        "name": "fastapi",
        "version": "1.0.0",
        "summary": "FastAPI framework, high performance.",
        "home_page": None,
        "project_urls": {"Homepage": "https://github.com/fastapi/fastapi"},
        "license_expression": "MIT",
        "requires_python": ">=3.9",
    },
    "urls": [{"upload_time_iso_8601": "2026-10-01T12:00:00.000000Z"}],
}

NPM_TYPES_REACT = {
    "name": "@types/react",
    "version": "19.2.0",
    "description": "TypeScript definitions for react",
    "homepage": "https://github.com/DefinitelyTyped/DefinitelyTyped",
    "license": "MIT",
}


@pytest.fixture
def registry(monkeypatch):
    """Serve fake registry responses and resolve hosts to a public IP."""
    responses: dict[str, httpx.Response] = {}
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return responses.get(str(request.url), httpx.Response(404))

    monkeypatch.setattr(
        package_info_module, "http_transport", httpx.MockTransport(handler)
    )
    monkeypatch.setattr(
        package_info_module, "resolve_host", lambda host, port: ["93.184.216.34"]
    )

    return responses, requests


async def lookup(**args) -> dict:
    return json.loads(await package_info.ainvoke(args))


@pytest.mark.asyncio
async def test_pypi_package_is_parsed(registry):
    responses, requests = registry
    responses["https://pypi.org/pypi/fastapi/json"] = httpx.Response(
        200, json=PYPI_FASTAPI
    )

    payload = await lookup(ecosystem="pypi", name="fastapi")

    assert payload["ok"] is True
    assert payload["result"] == {
        "ecosystem": "pypi",
        "name": "fastapi",
        "latest_version": "1.0.0",
        "released_at": "2026-10-01T12:00:00.000000Z",
        "summary": "FastAPI framework, high performance.",
        "homepage": "https://github.com/fastapi/fastapi",
        "license": "MIT",
        "requires_python": ">=3.9",
        "registry_url": "https://pypi.org/project/fastapi/",
    }
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_scoped_npm_package_is_parsed(registry):
    responses, requests = registry
    responses["https://registry.npmjs.org/@types%2Freact/latest"] = (
        httpx.Response(200, json=NPM_TYPES_REACT)
    )

    payload = await lookup(ecosystem="npm", name="@types/react")

    assert payload["ok"] is True
    assert payload["result"]["latest_version"] == "19.2.0"
    assert payload["result"]["license"] == "MIT"
    assert payload["result"]["released_at"] is None
    assert payload["result"]["registry_url"] == (
        "https://www.npmjs.com/package/@types/react"
    )


@pytest.mark.asyncio
async def test_unknown_package_is_reported(registry):
    payload = await lookup(ecosystem="pypi", name="no-such-package-xyz")

    assert payload["ok"] is False
    assert "No pypi package named 'no-such-package-xyz'" in payload["error"]


@pytest.mark.asyncio
async def test_redirects_are_not_followed(registry):
    responses, requests = registry
    responses["https://pypi.org/pypi/fastapi/json"] = httpx.Response(
        302, headers={"Location": "http://169.254.169.254/latest/meta-data"}
    )

    payload = await lookup(ecosystem="pypi", name="fastapi")

    assert payload["ok"] is False
    assert len(requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("ecosystem", "name"),
    [
        ("pypi", "../../admin"),
        ("pypi", "fast api"),
        ("pypi", "-leading-dash"),
        ("npm", "UpperCase"),
        ("npm", "@scope/../etc"),
        ("npm", "pkg?x=1"),
        ("cargo", "serde"),
    ],
)
async def test_invalid_names_are_rejected_before_any_request(
    registry, ecosystem, name
):
    _, requests = registry

    payload = await lookup(ecosystem=ecosystem, name=name)

    assert payload["ok"] is False
    assert payload["error"].startswith("Invalid tool input")
    assert requests == []


@pytest.mark.asyncio
async def test_registry_resolving_to_private_address_is_blocked(
    registry, monkeypatch
):
    _, requests = registry
    monkeypatch.setattr(
        package_info_module, "resolve_host", lambda host, port: ["10.0.0.5"]
    )

    payload = await lookup(ecosystem="pypi", name="fastapi")

    assert payload["ok"] is False
    assert "could not be reached safely" in payload["error"]
    assert requests == []


def test_only_registry_hosts_are_allowed():
    resolver = lambda host, port: ["93.184.216.34"]  # noqa: E731

    for ecosystem, name in [("pypi", "fastapi"), ("npm", "@types/react")]:
        validate_outbound_url(
            registry_url(ecosystem, name),
            package_info_module.REGISTRY_HOSTS,
            resolver,
        )

    with pytest.raises(UnsafeURLError):
        validate_outbound_url(
            "https://evil.example.com/pypi/fastapi/json",
            package_info_module.REGISTRY_HOSTS,
            resolver,
        )
