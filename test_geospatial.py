import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from datalayer.location_resolver import resolve_location
from datalayer.osm_client import get_business_density

test_locations = [
    "Karur, Tamil Nadu",
    "Bansur, Alwar",
    "Palakkad, Kerala",
    "Madhavaram, Andhra Pradesh",
    "Sonamura, Tripura"
]

for loc in test_locations:
    print(f"\n--- Testing Location: {loc} ---")
    
    loc_data = resolve_location(loc)
    print(f"Location Result: {loc_data}")
    
    if loc_data.get("lat") and loc_data.get("lon"):
        business_type = "grocery"
        density_data = get_business_density(loc_data["lat"], loc_data["lon"], business_type)
        print(f"Business Density Result ({business_type}): {density_data}")
        
        # Test caching
        print("Testing cache...")
        cached_density = get_business_density(loc_data["lat"], loc_data["lon"], business_type)
        assert cached_density is density_data
    else:
        print("Could not resolve lat/lon for business density test.")
