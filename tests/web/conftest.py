import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from waybill_generator.web.app import create_app

FIXTURES = Path(__file__).parent.parent / "fixtures"

# A valid car form as a browser would post it (PRR-12345 in the fixtures).
CAR_FORM = {"road": "PRR", "car_number": "12345", "aar_code": "XM", "capacity_tons": "50",
            "capacity_cuft": "3020", "length_ft": "40", "active": "on"}


@pytest.fixture
def data_dir(tmp_path):
    """A private, writable copy of tests/fixtures."""
    target = tmp_path / "data"
    shutil.copytree(FIXTURES, target)
    return target


@pytest.fixture
def client(data_dir):
    return TestClient(create_app(data_dir), follow_redirects=False)


def follow(client, response):
    """GET the page a 303 redirect points at."""
    assert response.status_code == 303, response.text[:300]
    return client.get(response.headers["location"])
