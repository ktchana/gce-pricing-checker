import pytest
import json
from unittest.mock import MagicMock
from main import get_pricing
import main

@pytest.fixture
def target_config():
    return {
        "family": "n4",
        "vcpus": 32,
        "ram_gb": 256.0,
        "search_cpu": "n4 instance core",
        "search_ram": "n4 instance ram"
    }

def test_get_pricing_cache_hit(mocker, target_config):
    # Mock `os.path.exists` to return True for the cache file
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("time.time", return_value=12345678)
    
    # Mock data to simulate the pricing cache
    cache_key = "n4_europe-west2"
    fake_cache_data = {
        cache_key: {
            "timestamp": 12345678,
            "cpu_price": 1.5,
            "ram_price": 0.05
        }
    }
    mocker.patch("builtins.open", mocker.mock_open(read_data=json.dumps(fake_cache_data)))
    
    # Mock fetch to ensure it is NOT called
    mock_fetch = mocker.patch("main.fetch_and_cache_skus")
    
    cpu, ram = get_pricing(target_config, "test-project", "europe-west2")
    
    assert cpu == 1.5
    assert ram == 0.05
    mock_fetch.assert_not_called()

def test_get_pricing_catalogue_search(mocker, target_config):
    # Mock cache path miss
    mocker.patch("os.path.exists", return_value=False)
    mocker.patch("os.makedirs")
    mocker.patch("builtins.open", mocker.mock_open())
    
    # Provide a fake catalogue array from `fetch_and_cache_skus`
    fake_skus = [
        {
            "description": "N4 Instance Core running in London",
            "service_regions": ["europe-west2"],
            "units": 0,
            "nanos": 150000000 # 0.15
        },
        {
            "description": "N4 Instance Ram running in London",
            "service_regions": ["europe-west2"],
            "units": 0,
            "nanos": 50000000  # 0.05
        }
    ]
    mocker.patch("main.fetch_and_cache_skus", return_value=fake_skus)
    
    cpu, ram = get_pricing(target_config, "test-project", "europe-west2")
    
    assert cpu == 0.15
    assert ram == 0.05

def test_get_pricing_catalogue_missing(mocker, target_config):
    mocker.patch("os.path.exists", return_value=False)
    mocker.patch("main.fetch_and_cache_skus", return_value=[])
    
    cpu, ram = get_pricing(target_config, "test-project", "europe-west2")
    
    # Missing from API -> returns 0, 0
    assert cpu == 0
    assert ram == 0
