import time
import requests

def resolve_location(location_text: str) -> dict:
    """
    Resolves a location text to geospatial and administrative details using Nominatim API.
    """
    # Nominatim API endpoint
    url = "https://nominatim.openstreetmap.org/search"
    
    # Respect 1 req/s usage policy
    time.sleep(1.1)

    headers = {
        # Nominatim's usage policy requires a real, identifying User-Agent —
        # spoofing a browser is against their rules and gets the IP blocked.
        "User-Agent": "Jaldhrishti-SIH2026/1.0 (hackathon rural-advisory bot)"
    }
    params = {
        "q": location_text,
        "format": "jsonv2",
        "addressdetails": 1,
        "countrycodes": "IN",
        "limit": 1,
        # Restrict matches to actual settlements (village/town/city/etc.),
        # not businesses or POIs whose name happens to contain the query
        # text (e.g. a "Karur Vysya Bank" branch in Chennai matching "Karur").
        "featureType": "settlement",
    }

    try:
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Error calling Nominatim: {e}")
        data = []

    result = {
        "village": None,
        "block": None,
        "district": None,
        "state": None,
        "lgd_code": None, # Nominatim doesn't have LGD codes natively
        "lat": None,
        "lon": None,
        "confidence": "low"
    }

    if data:
        item = data[0]
        result["lat"] = float(item.get("lat"))
        result["lon"] = float(item.get("lon"))
        
        # Calculate confidence based on type or importance
        place_rank = item.get("place_rank", 30)
        importance = item.get("importance", 0.0)
        
        if item.get("type") in ["village", "town", "city", "administrative", "neighbourhood", "suburb"]:
            result["confidence"] = "high"
        elif importance > 0.3:
             result["confidence"] = "high"

        address = item.get("address", {})
        
        # Nominatim returns various keys for village/town/city
        result["village"] = address.get("village") or address.get("hamlet") or address.get("town") or address.get("city") or address.get("neighbourhood")
        # Block is sometimes county, state_district or subdistrict
        result["block"] = address.get("county") or address.get("subdistrict") or address.get("region")
        result["district"] = address.get("state_district") or address.get("county") or address.get("district")
        result["state"] = address.get("state")
        
        # Fill None if not present
        if not result["village"]:
            result["village"] = "Unknown"
        if not result["district"]:
            result["district"] = "Unknown"
        if not result["state"]:
            result["state"] = "Unknown"

    return result
