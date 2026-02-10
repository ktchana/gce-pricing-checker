import pytest
from main import parse_instance

def test_parse_standard_instance():
    result = parse_instance("n2d-standard-16")
    assert result is not None
    assert result["family"] == "n2d"
    assert result["vcpus"] == 16
    assert result["ram_gb"] == 16 * 4.0
    assert result["search_cpu"] == "n2d amd instance core"
    assert result["search_ram"] == "n2d amd instance ram"

def test_parse_highmem_instance():
    result = parse_instance("n4-highmem-32")
    assert result is not None
    assert result["family"] == "n4"
    assert result["vcpus"] == 32
    assert result["ram_gb"] == 32 * 8.0

def test_parse_memory_optimized():
    result = parse_instance("m3-ultramem-32")
    assert result is not None
    assert result["family"] == "m3"
    assert result["vcpus"] == 32
    assert result["ram_gb"] == 32 * 30.5
    assert result["search_cpu"] == "m3 memory-optimized instance core"

def test_parse_case_insensitivity():
    result = parse_instance("N4-HIGHMEM-32")
    assert result is not None
    assert result["family"] == "n4"
    assert result["vcpus"] == 32

def test_malformed_string():
    assert parse_instance("n4-highmem") is None
    assert parse_instance("random-string") is None
    assert parse_instance("n4-highmem-abc") is None

def test_unsupported_family_or_shape(capsys):
    assert parse_instance("z1-standard-4") is None
    captured = capsys.readouterr()
    assert "not currently defined" in captured.out

    assert parse_instance("c2-highmem-4") is None
    captured = capsys.readouterr()
    assert "not found for family" in captured.out
