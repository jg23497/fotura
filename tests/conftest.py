from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def stub_user_dirs(tmp_path):
    user_data_path = tmp_path / "user_data"
    user_config_path = tmp_path / "user_config"
    user_data_path.mkdir()
    user_config_path.mkdir()

    with (
        patch("fotura.importer.user_data_dir", return_value=user_data_path),
        patch("fotura.importer.user_config_dir", return_value=user_config_path),
    ):
        yield user_data_path, user_config_path


@pytest.fixture
def target_root(fs) -> Path:
    directory = Path("~/target")
    fs.create_dir(directory)
    return directory
