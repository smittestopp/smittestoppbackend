#!/usr/bin/env python3
"""Get azure ips for regions and display them as JSON

Usage:

    python3 getazureips.py > azureips.json

"""

import json
import sys

import requests

# weekly url is really: https://www.microsoft.com/en-us/download/confirmation.aspx?id=56519
# need to parse out "click here to download manually" link
weekly_download_url = "https://download.microsoft.com/download/7/1/D/71D86715-5596-4529-9B13-DA13A5DE5B63/ServiceTags_Public_20200427.json"


regions = {"AzureCloud.northeurope", "AzureCloud.westeurope"}


def get_ips():
    r = requests.get(weekly_download_url)
    r.raise_for_status()
    data = r.json()
    ips = []
    for region in data["values"]:
        if region["name"] in regions:
            ips.extend(region["properties"]["addressPrefixes"])
    json.dump(sorted(ips), sys.stdout, indent=1)


if __name__ == "__main__":
    get_ips()
