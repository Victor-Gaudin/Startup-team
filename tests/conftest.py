import json

import httpx2
import pytest

from dropkit.config import Settings
from dropkit.db import DB


@pytest.fixture
def settings(tmp_path):
    return Settings(
        ebay_client_id="cid", ebay_client_secret="secret", ebay_ru_name="ru", marketplace="EBAY_US",
        fulfillment_policy_id="F1", payment_policy_id="P1", return_policy_id="R1",
        aliexpress_app_key="ak", aliexpress_app_secret="as", aliexpress_access_token="at",
        target_margin=0.20, min_margin=0.10, promoted_rate=0.04, db_path=str(tmp_path / "t.db"),
    )


@pytest.fixture
def db(settings):
    return DB(settings.db_path)


class Router:
    """Tiny request router for httpx2.MockTransport."""

    def __init__(self):
        self.routes = []
        self.calls = []

    def add(self, method, path_contains, responder):
        self.routes.append((method, path_contains, responder))

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.calls.append(request)
        url = str(request.url)
        for method, frag, responder in self.routes:
            if request.method == method and frag in url:
                result = responder(request) if callable(responder) else responder
                if isinstance(result, httpx2.Response):
                    return result
                status, body = result if isinstance(result, tuple) else (200, result)
                return httpx2.Response(status, json=body)
        return httpx2.Response(404, json={"errors": [{"errorId": 0, "message": f"no route {request.method} {url}"}]})

    def body(self, request):
        return json.loads(request.content) if request.content else None


@pytest.fixture
def router():
    return Router()


@pytest.fixture
def http(router):
    return httpx2.Client(transport=httpx2.MockTransport(router))
