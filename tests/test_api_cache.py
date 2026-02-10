import pytest
import os
import json
import time
from unittest.mock import MagicMock
from main import fetch_and_cache_skus, CACHE_DIR, SKU_CACHE_FILE, CACHE_EXPIRY

@pytest.fixture
def mock_cache_env(mocker):
    # Ensure tests don't write to real cache files
    test_cache_file = "tests/test_sku_cache.json"
    mocker.patch("main.SKU_CACHE_FILE", test_cache_file)
    
    yield test_cache_file
    
    # We don't need to os.remove because os.path.exists is mocked 
    # and open is mocked, so the file is never actually created.

def test_fetch_cache_hit_fresh(mocker, mock_cache_env):
    # Mock os.path.exists to True for the cache file
    mocker.patch("os.path.exists", return_value=True)
    
    # Create fake cache data
    fake_data = {"timestamp": time.time(), "skus": [{"description": "fake sku"}]}
    mocker.patch("builtins.open", mocker.mock_open(read_data=json.dumps(fake_data)))
    
    mock_client = mocker.patch("main.billing_v1.CloudCatalogClient")
    
    result = fetch_and_cache_skus()
    
    assert result == [{"description": "fake sku"}]
    mock_client.assert_not_called()

def test_fetch_cache_miss_expired(mocker, mock_cache_env):
    mocker.patch("os.path.exists", return_value=True)
    
    # Create expired cache data (2 days old)
    fake_data = {"timestamp": time.time() - (CACHE_EXPIRY * 2), "skus": [{"description": "fake sku"}]}
    
    # We need a proper mocked open that acts like a real open sequence
    mocker.patch("builtins.open", mocker.mock_open(read_data=json.dumps(fake_data)))
    
    # Mock the API client
    mock_client = mocker.patch("main.billing_v1.CloudCatalogClient")
    mock_instance = MagicMock()
    mock_client.return_value = mock_instance
    
    # Fake API response
    fake_sku = MagicMock()
    fake_sku.description = "api sku"
    fake_sku.service_regions = ["region1"]
    fake_sku.pricing_info = [MagicMock()]
    fake_sku.pricing_info[0].pricing_expression.tiered_rates = [MagicMock()]
    fake_sku.pricing_info[0].pricing_expression.tiered_rates[0].unit_price.units = 1
    fake_sku.pricing_info[0].pricing_expression.tiered_rates[0].unit_price.nanos = 500000000
    mock_instance.list_skus.return_value = [fake_sku]
    
    # We also need to mock `os.makedirs` so it doesn't fail trying to create fake directories
    mocker.patch("os.makedirs")
    
    result = fetch_and_cache_skus()
    
    assert len(result) == 1
    assert result[0]["description"] == "api sku"
    assert result[0]["units"] == 1
    assert result[0]["nanos"] == 500000000
    mock_client.assert_called_once()
