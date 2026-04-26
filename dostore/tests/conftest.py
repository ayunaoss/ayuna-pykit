"""conftest.py - Pytest configuration and fixtures for ayuna_dostore tests."""

import pytest


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use uvloop for better async performance in tests."""
    import uvloop

    return uvloop.EventLoopPolicy()
