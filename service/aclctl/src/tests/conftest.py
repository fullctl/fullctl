import os

import pytest_filedata

from tests.fixtures import *  # noqa: F401, F403

pytest_filedata.setup(os.path.dirname(__file__))


def pytest_generate_tests(metafunc):
    for fixture in metafunc.fixturenames:
        if fixture.startswith("data_"):
            data = pytest_filedata.get_data(fixture)
            metafunc.parametrize(fixture, list(data.values()), ids=list(data.keys()))
