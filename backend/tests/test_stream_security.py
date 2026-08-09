"""Security regression tests for task-scoped SSE access."""

from app.core.security import create_access_token, create_stream_token, verify_stream_token


def test_stream_token_is_scoped_to_one_task():
    token = create_stream_token("task-1", "user-1")

    assert verify_stream_token(token, "task-1") is True
    assert verify_stream_token(token, "task-2") is False


def test_access_token_cannot_be_used_as_stream_token():
    token = create_access_token({"sub": "user-1"})
    assert verify_stream_token(token, "task-1") is False
