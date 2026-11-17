import pytest
from contratos import ejemplos_spec


@pytest.fixture
def ejemplos() -> dict[str, dict]:
    return ejemplos_spec()
