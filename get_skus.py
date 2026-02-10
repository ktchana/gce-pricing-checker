import os
import json
import time
from google.cloud import billing_v1

SKU_CACHE_FILE = "sku_cache.json"
CACHE_EXPIRY = 86400  # 1 day in seconds

def get_skus():
    if os.path.exists(SKU_CACHE_FILE):
        try:
            with open(SKU_CACHE_FILE, "r") as f:
                data = json.load(f)
            if time.time() - data.get("timestamp", 0) < CACHE_EXPIRY:
                print("✅ Loaded SKUs from local cache")
                return data.get("skus", [])
        except Exception as e:
            print(f"⚠️ SKU Cache read error: {e}")

    print("🌐 Fetching SKUs from GCP API...")
    client = billing_v1.CloudCatalogClient()
    service_id = "6F81-5844-456A"
    request = billing_v1.ListSkusRequest(parent=f"services/{service_id}")
    page_result = client.list_skus(request=request)
    
    skus = []
    # limit just to grab a few for testing
    count = 0
    for sku in page_result:
        try:
            price_info = sku.pricing_info[0].pricing_expression.tiered_rates[0]
            skus.append({
                "description": sku.description,
                "service_regions": list(sku.service_regions),
                "units": price_info.unit_price.units,
                "nanos": price_info.unit_price.nanos
            })
            count += 1
            if count > 10: break
        except IndexError:
            pass
            
    try:
        with open(SKU_CACHE_FILE, "w") as f:
            json.dump({"timestamp": time.time(), "skus": skus}, f, indent=4)
    except Exception as e:
        print(f"⚠️ SKU Cache write error: {e}")
        
    return skus

get_skus()
