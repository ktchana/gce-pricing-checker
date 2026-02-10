import sys
import os
import json
import time
import argparse
from dotenv import load_dotenv
from google.cloud import billing_v1

# Load environment variables from .env file
load_dotenv()

CACHE_DIR = "caches"
CACHE_FILE = os.path.join(CACHE_DIR, "pricing_cache.json")
SKU_CACHE_FILE = os.path.join(CACHE_DIR, "sku_cache.json")
CACHE_EXPIRY = 86400  # 1 day in seconds

import os
import json

# Setup config path and load MACHINE_SPECS
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config", "machine_specs.json")
with open(CONFIG_FILE, "r") as f:
    MACHINE_SPECS = json.load(f)

# ==========================================
# 2. LOGIC TO PARSE INPUT
# ==========================================
def parse_instance(instance_type):
    try:
        parts = instance_type.lower().split('-')
        if len(parts) < 3: return None
        
        family = parts[0]
        shape = parts[1]
        vcpus = int(parts[2])

        if family not in MACHINE_SPECS:
            print(f"❌ Family '{family}' not currently defined.")
            return None

        specs = MACHINE_SPECS[family]
        
        if shape not in specs["ratios"]:
            print(f"❌ Shape '{shape}' not found for family '{family}'.")
            return None
            
        ram_gb = vcpus * specs["ratios"][shape]
        
        return {
            "family": family,
            "vcpus": vcpus,
            "ram_gb": ram_gb,
            "search_cpu": specs["search_cpu"],
            "search_ram": specs["search_ram"]
        }

    except Exception as e:
        print(f"Error parsing: {e}")
        return None

# ==========================================
# 3. SKU FETCH LOGIC
# ==========================================
def fetch_and_cache_skus():
    if os.path.exists(SKU_CACHE_FILE):
        try:
            with open(SKU_CACHE_FILE, "r") as f:
                data = json.load(f)
            if time.time() - data.get("timestamp", 0) < CACHE_EXPIRY:
                print("✅ Loaded SKUs from local catalog cache")
                return data.get("skus", [])
        except Exception as e:
            print(f"⚠️ SKU Cache read error: {e}")

    print("🌐 Fetching complete SKU catalog from GCP API (this might take a few seconds)...")
    client = billing_v1.CloudCatalogClient()
    service_id = "6F81-5844-456A" 
    request = billing_v1.ListSkusRequest(parent=f"services/{service_id}")
    page_result = client.list_skus(request=request)
    
    simplified_skus = []
    for sku in page_result:
        try:
            price_info = sku.pricing_info[0].pricing_expression.tiered_rates[0]
            simplified_skus.append({
                "description": sku.description,
                "service_regions": list(sku.service_regions),
                "units": price_info.unit_price.units,
                "nanos": price_info.unit_price.nanos
            })
        except IndexError:
            # Skip SKUs without pricing structure
            pass

    # Save to local cache
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        with open(SKU_CACHE_FILE, "w") as f:
            json.dump({
                "timestamp": time.time(),
                "skus": simplified_skus
            }, f, indent=2)
    except Exception as e:
        print(f"⚠️ SKU Cache write error: {e}")

    return simplified_skus

# ==========================================
# 4. PRICING FETCH LOGIC
# ==========================================
def get_pricing(target_config, project_id, region):
    cache_key = f"{target_config['family']}_{region}"
    
    # Check cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                cache_data = json.load(f)
            
            if cache_key in cache_data:
                entry = cache_data[cache_key]
                if time.time() - entry.get("timestamp", 0) < CACHE_EXPIRY:
                    print(f"✅ Loaded {target_config['family']} pricing from local cache ({region})")
                    return entry.get("cpu_price", 0), entry.get("ram_price", 0)
        except Exception as e:
            print(f"⚠️ Cache read error: {e}")

    skus = fetch_and_cache_skus()
    
    cpu_price = 0
    ram_price = 0
    found_cpu = False
    found_ram = False

    print(f"🔎 Searching cached SKUs in {region} for '{target_config['family']}'...")
    
    exclusions = ["spot", "preemptible", "sole tenancy", "premium", "commitment"]
    
    # Prevents N2 from matching N2D
    family_guard = [f"{target_config['family']}d", f"{target_config['family']}a"] 

    for sku in skus:
        if found_cpu and found_ram: break
        if region not in sku["service_regions"]: continue

        desc = sku["description"].lower()
        
        if any(x in desc for x in exclusions): continue
        if any(x in desc for x in family_guard): continue

        # MATCH CPU
        if not found_cpu and target_config["search_cpu"] in desc:
            cpu_price = (sku["units"] + sku["nanos"] / 1e9)
            found_cpu = True
            print(f"   ✅ found cpu: {sku['description']}")

        # MATCH RAM
        if not found_ram and target_config["search_ram"] in desc:
            ram_price = (sku["units"] + sku["nanos"] / 1e9)
            found_ram = True
            print(f"   ✅ found ram: {sku['description']}")

    # Write to cache
    if cpu_price > 0 and ram_price > 0:
        os.makedirs(CACHE_DIR, exist_ok=True)
        cache_data = {}
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r") as f:
                    cache_data = json.load(f)
            except Exception:
                pass
                
        cache_data[cache_key] = {
            "cpu_price": cpu_price,
            "ram_price": ram_price,
            "timestamp": time.time()
        }
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump(cache_data, f, indent=4)
        except Exception as e:
            print(f"⚠️ Cache write error: {e}")

    return cpu_price, ram_price

# ==========================================
# 5. MAIN CALCULATOR
# ==========================================
def calculate_cost(instance_type, region=None):
    if region is None:
        region = os.getenv("GCP_REGION", "europe-west2")
        
    config = parse_instance(instance_type)
    if not config: return None

    print(f"\n--- 💰 Estimating {instance_type} ---")
    print(f"Specs: {config['vcpus']} vCPUs | {config['ram_gb']} GB RAM")

    project_id = os.getenv("GCP_PROJECT_ID", "ktchana-thg-1")
    cpu_cost, ram_cost = get_pricing(config, project_id, region)
    
    if cpu_cost == 0 and ram_cost == 0:
        print("❌ Could not find pricing SKUs. (Check region availability?)")
        return None

    total_hourly = (cpu_cost * config["vcpus"]) + (ram_cost * config["ram_gb"])
    total_monthly = total_hourly * 730

    print(f"Total Hourly:  ${total_hourly:.4f}")
    print(f"Total Monthly: ${total_monthly:.2f}")
    
    return total_monthly

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Estimate GCP Compute Engine Costs")
    parser.add_argument(
        "instance_type", 
        nargs="?",
        help="The instance type to parse (e.g., n4-highmem-32, m3-ultramem-32, etc.)"
    )
    parser.add_argument(
        "-f", "--file",
        help="Path to a text file containing instance types (one per line)",
        default=None
    )
    parser.add_argument(
        "--region", 
        help="The GCP region to estimate for (e.g., europe-west2)",
        default=None
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Print only the monthly amount as the output but nothing else."
    )
    parser.add_argument(
        "--print-name",
        action="store_true",
        help="When in quiet mode, prepend the instance name to the output (e.g., n4-standard-16,603.84)"
    )
    
    args = parser.parse_args()
    
    if not args.instance_type and not args.file:
        parser.error("You must provide either an instance_type or a --file argument.")

    instances = []
    if args.file:
        if os.path.exists(args.file):
            with open(args.file, 'r') as f:
                instances.extend([line.strip() for line in f if line.strip() and not line.strip().startswith("#")])
        else:
            print(f"Error: File '{args.file}' not found.")
            sys.exit(1)
            
    if args.instance_type:
        instances.append(args.instance_type)
    
    original_stdout = sys.stdout
    for instance in instances:
        if args.quiet:
            sys.stdout = open(os.devnull, 'w')
            
        monthly_cost = calculate_cost(instance, region=args.region)
        
        if args.quiet:
            sys.stdout.close()
            sys.stdout = original_stdout
            if monthly_cost is not None:
                if args.print_name:
                    print(f"{instance},{monthly_cost:.2f}")
                else:
                    print(f"{monthly_cost:.2f}")