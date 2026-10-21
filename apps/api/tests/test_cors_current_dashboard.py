"""CORS integration checks for the verified live web operations origin.

Regression: the old immutable Vercel URL worked while the current main
dashboard received a 400 from the API preflight. This test does not need DB.
"""

from fastapi.testclient import TestClient

from app.main import create_application


def test_current_main_dashboard_may_call_order_api() -> None:
    app = create_application()
    client = TestClient(app)
    origin = "https://uniserve-web-dashboard-git-main-pakmultilinks-dot.vercel.app"
    response = client.options(
        "/api/v1/orders/cafeteria/test",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-credentials"] == "true"


def test_similar_attacker_origin_is_not_whitelisted() -> None:
    app = create_application()
    client = TestClient(app)
    response = client.options(
        "/api/v1/orders/cafeteria/test",
        headers={
            "Origin": "https://uniserve-web-dashboard-git-main-pakmultilinks-dot.vercel.app.attacker.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 400
    assert response.headers.get("access-control-allow-origin") is None
