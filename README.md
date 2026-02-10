# GCP Compute Engine Pricing Client

> **Disclaimer:** This is not an official Google Cloud supported tool. It is based on the Google Cloud Billing API and the [publicly available SKU lists](https://cloud.google.com/skus?filter=6F81-5844-456A). It calculates strictly base on-demand prices and does not take into account any contract-specific discounts, reservations, committed use discounts, prepayments, or single tenancy rates.

A command-line Python utility to dynamically calculate the hourly and monthly on-demand costs of Google Cloud Compute Engine instances.

## Background
Google Cloud provides a robust billing API, but calculating the exact price of an instance requires matching specific SKU descriptions, parsing tiered pricing arrays, and multiplying base unit strings. This tool abstracts that complexity. 

It takes an instance type (e.g., `n4-highmem-32`), breaks it down into required vCPUs and RAM based on official GCP hardware ratios, and searches the live Google Cloud Catalog API for the exact on-demand pricing in your specified region. 

To ensure fast execution, the tool implements a **two-layer local caching system** (expiring every 24 hours):
1. **Catalog Cache** (`caches/sku_cache.json`): Caches the region's entire compute SKU catalog to avoid repeated 5-second API payloads.
2. **Pricing Cache** (`caches/pricing_cache.json`): Caches the final parsed vCPU and RAM price calculations for instant subsequent lookups.

## Features
- **Supported Families:** General Purpose (N1, N2, N2D, N4, N4A, N4D, E2), Compute-Optimized (C2, C3, C3D, C4, C4A, C4D), and Memory-Optimized (M3).
- **Auto Resource Calculation:** Dynamically calculates total RAM based on standard GCP CPU-to-RAM ratios for standard, highmem, and highcpu profiles.
- **Environment Variables:** Set defaults via a `.env` file for project and region context without exposing secrets in your script.

## Limitations
- **No Validation:** The tool does not validate whether the input machine types actually exist. It merely relies on predefined CPU-to-Memory ratios to determine the number of vCPUs and Memory, multiplying these by the SKU unit rate to produce a price.
- **No Custom Machine Types:** It does not yet support custom machine types.
- **No OS License Costs:** The calculation is purely based on vCPU and Memory and does not include OS license costs.

## Installation

### 1. Prerequisites
- Python 3.11+
- Authenticated Google Cloud credentials on your machine. You can set this up using the Google Cloud CLI:
  ```bash
  gcloud auth application-default login
  ```

### 2. Install Dependencies
Clone this directory and install the required Python packages (`google-cloud-billing` and `python-dotenv`):
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy the `.env.example` file to `.env` in the project directory and update the values to set your baseline defaults:
```bash
cp .env.example .env
```

### 4. Testing (Optional)
This project uses `pytest` for unit testing across parsing, pricing, caching, and CLI operations. Unit tests use `pytest-mock` to avoid making live Google Cloud API calls or generating real cache files:
```bash
# Install testing dependencies
pip install pytest pytest-mock

# Run the test suite
python -m pytest tests/
```

## Usage

Run the `main.py` script and provide the instance type as a positional argument.

### Basic Estimate
This uses the default region specified in your `.env` file:
```bash
python main.py m3-ultramem-32
```

### Region Override
You can override the `.env` region dynamically by using the `--region` flag:
```bash
python main.py n4-highmem-32 --region us-central1
```

### Quiet Mode (Output Only Cost)
If you only want the monthly cost printed (e.g., for piping into other tools), use the `-q` or `--quiet` flag:
```bash
python main.py m3-ultramem-32 -q
```

### Quiet Mode with Instance Name Included
To output the instance name alongside the monthly cost in a CSV format, combine `--quiet` with `--print-name`:
```bash
python main.py n4-standard-16 -q --print-name
```
*Output:* `n4-standard-16,603.84`

### Process a List of Instances from a File
You can process multiple instances at once by passing a text file containing one instance type per line using the `-f` or `--file` flag. Useful for batch generating CSV files:
```bash
python main.py -f list.txt -q --print-name > prices.csv
```

### Display Help
```bash
python main.py -h
```
