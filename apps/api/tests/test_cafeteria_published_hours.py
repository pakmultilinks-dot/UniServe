from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.core.exceptions import ValidationError
from app.modules.orders.service import OrderService


def cafe(hours="07:00-16:00"):
    return SimpleNamespace(operating_hours=hours, timezone="Asia/Karachi", closing_time=None)


@pytest.mark.parametrize("instant,allowed", [
    ("2026-10-26T01:59:00+00:00", False),
    ("2026-10-26T02:00:00+00:00", True),
    ("2026-10-26T10:59:00+00:00", True),
    ("2026-10-26T11:00:00+00:00", False),
    ("2026-10-26T12:48:00+00:00", False),
])
def test_immediate_local_hours(instant, allowed):
    now = datetime.fromisoformat(instant)
    with patch("app.modules.orders.service.datetime") as clock:
        clock.now.side_effect = lambda tz=UTC: now.astimezone(tz)
        service = OrderService(None)
        if allowed:
            service._validate_immediate_hours(cafe())
        else:
            with pytest.raises(ValidationError, match="outside its operating hours"):
                service._validate_immediate_hours(cafe())


@pytest.mark.parametrize("slot", ["06:59", "16:00", "17:00"])
def test_schedule_rejects_outside_published_hours(slot):
    now = datetime(2026, 10, 26, 0, tzinfo=UTC)
    with patch("app.modules.orders.service.datetime", wraps=datetime) as clock:
        clock.now.side_effect = lambda tz=UTC: now.astimezone(tz)
        with pytest.raises(ValidationError, match="within cafeteria operating hours"):
            OrderService(None)._validate_scheduled_order_time(slot, cafe())


def test_legacy_missing_hours_remains_compatible():
    OrderService(None)._validate_immediate_hours(cafe(None))
