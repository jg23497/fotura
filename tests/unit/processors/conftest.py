from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fotura.utils.synchronized_counter import SynchronizedCounter
from tests.helpers.google_photos import create_client_secret, create_credentials


@pytest.fixture
def tally():
    return SynchronizedCounter({"errored": 0})


@pytest.fixture(autouse=True)
def mock_photoslibrary_service():
    with patch("fotura.integrations.google_photos.client.build") as mock_build:
        mock_service = MagicMock()
        mock_service._http = MagicMock(
            credentials=MagicMock(token="ya29.default-token")
        )
        mock_build.return_value = mock_service
        yield mock_build


@pytest.fixture
def client_secret():
    return create_client_secret()


@pytest.fixture
def cached_credentials_expired():
    return create_credentials(expiry=datetime.now() - timedelta(days=1))


@pytest.fixture
def cached_credentials_valid():
    return create_credentials(expiry=datetime.now() + timedelta(days=1))


@pytest.fixture
def secrets_dir(fs):
    secrets_dir = Path(".secrets")
    fs.create_dir(secrets_dir)
    return secrets_dir
