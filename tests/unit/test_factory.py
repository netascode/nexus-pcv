# Copyright: (c) 2026, Noppanut Ploywong <nploywon@cisco.com>

from typing import Any, NoReturn

import httpx
import pytest

from nexus_pcv.nd import factory
from nexus_pcv.nd.base import NDBackend
from nexus_pcv.nd.legacy import LegacyNDI
from nexus_pcv.nd.nd4 import ND4

from .helpers import HOST, json_response

pytestmark = pytest.mark.unit


def patch_version_endpoint(
    monkeypatch: pytest.MonkeyPatch, response: httpx.Response
) -> None:
    """Make the unauthenticated /version.json probe return ``response``"""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/version.json"
        return response

    # Bind the real class before patching, otherwise the replacement recurses
    # into itself when it builds the mock-backed client.
    real_client = httpx.Client

    def fake_client(*args: Any, **kwargs: Any) -> httpx.Client:
        return real_client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(factory.httpx, "Client", fake_client)


def build(monkeypatch: pytest.MonkeyPatch, response: httpx.Response) -> NDBackend:
    patch_version_endpoint(monkeypatch, response)
    return factory.create_backend(HOST, "user", "pass", "local", 15)  # nosec B106


def test_major_4_selects_the_nd4_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"major": 4, "minor": 2, "build_version": "4.2.1.10", "product_id": "nd"}
    assert isinstance(build(monkeypatch, json_response(payload)), ND4)


def test_major_3_selects_the_legacy_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"major": 3, "minor": 2, "build_version": "3.2.2f", "product_id": "nd"}
    assert isinstance(build(monkeypatch, json_response(payload)), LegacyNDI)


def test_major_5_selects_the_nd4_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Detection is >= 4, so a future release does not silently fall back"""
    payload = {"major": 5, "minor": 0}
    assert isinstance(build(monkeypatch, json_response(payload)), ND4)


def test_missing_version_endpoint_falls_back_to_legacy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Releases predating /version.json are legacy by definition"""
    assert isinstance(build(monkeypatch, httpx.Response(404)), LegacyNDI)


def test_unparseable_version_falls_back_to_legacy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert isinstance(build(monkeypatch, json_response({"foo": "bar"})), LegacyNDI)


def test_force_version_skips_detection(monkeypatch: pytest.MonkeyPatch) -> None:
    """The escape hatch must not consult the network at all"""

    def explode(*args: Any, **kwargs: Any) -> NoReturn:
        raise AssertionError("detection should have been skipped")

    monkeypatch.setattr(factory, "detect_major_version", explode)

    backend = factory.create_backend(
        HOST,
        "user",
        "pass",  # nosec B106
        "local",
        15,
        force_version=4,
    )
    assert isinstance(backend, ND4)
