import pytest
from medintell import MedIntell, MedIntellError


def test_constructs_resources():
    mi = MedIntell(api_key="mi_live_test")
    for r in ["organizations", "facilities", "departments", "doctors", "payers", "patients", "visits", "ingest"]:
        assert hasattr(mi, r)
    assert callable(mi.health)
    assert callable(mi.patients.iterate)


def test_requires_api_key():
    with pytest.raises(MedIntellError):
        MedIntell(api_key="")
