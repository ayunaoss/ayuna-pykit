"""
conftest.py - Pytest configuration and fixtures for ayuna_secrets tests.
"""

import pytest
from cryptography.fernet import Fernet


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use uvloop for better async performance in tests."""
    import uvloop

    return uvloop.EventLoopPolicy()


@pytest.fixture
def fernet_key() -> str:
    """Generate a valid Fernet key for encryption tests."""
    return Fernet.generate_key().decode()
