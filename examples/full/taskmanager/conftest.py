import pytest


@pytest.fixture(autouse=True)
def _raise_on_nplus1(settings):
    settings.NPLUS1_RAISE = True
