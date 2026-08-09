from datetime import datetime, timedelta, timezone

from app.services.investment_crm_service import _audit_value, _utc_naive


def test_utc_naive_converts_an_aware_datetime_to_utc():
    source = datetime(
        2026,
        7,
        30,
        17,
        30,
        tzinfo=timezone(timedelta(hours=8)),
    )

    assert _utc_naive(source) == datetime(2026, 7, 30, 9, 30)


def test_utc_naive_keeps_naive_datetime_and_none():
    source = datetime(2026, 7, 30, 9, 30)

    assert _utc_naive(source) is source
    assert _utc_naive(None) is None


def test_audit_value_serializes_datetime():
    source = datetime(2026, 7, 30, 9, 30)

    assert _audit_value(source) == "2026-07-30T09:30:00"
