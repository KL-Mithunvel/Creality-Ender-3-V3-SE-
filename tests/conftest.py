import pytest

from magnet_embed.config import load_config


@pytest.fixture
def config() -> dict:
    """The committed default configuration."""
    return load_config()
