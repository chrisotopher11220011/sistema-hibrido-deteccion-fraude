import pytest
from simulacion import simular


@pytest.fixture
def simulador():
    return simular
