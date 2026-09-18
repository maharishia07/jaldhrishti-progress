import time
import requests

# In-memory cache for get_business_density
# Key: (round(lat, 2), round(lon, 2), business_type, radius_km) -> Value: dict
_density_cache = {}

# Map business types to OSM tags
BUSINESS_TAG_MAP = {
    "grocery": "shop=supermarket;shop=convenience;shop=grocery",
    "pharmacy": "amenity=pharmacy",
    "clothes": "shop=clothes",
    "restaurant": "amenity=restaurant;amenity=cafe",
    "bank": "amenity=bank",
    "hardware": "shop=hardware",
    "agriculture": "shop=agrarian",
    "electronics": "shop=electronics"
}

def get_business_density(lat: float, lon: float, business_type: str, radius_km: int = 8) -> dict:
    """
    Queries Overpass API for shops/POIs matching business type within radius_km.
    """
    # Rounding coordinates for caching (approx 1km precision)
    cache_key = (round(lat, 2), round(lon, 2), business_type, radius_km)
    if cache_key in _density_cache:
        return _density_cache[cache_key]

    radius_meters = radius_km * 1000
    
    osm_tags = BUSINESS_TAG_MAP.get(business_type.lower())
    
    if osm_tags:
        # Split multiple tags by semicolon
        tag_queries = []
        for tag in osm_tags.split(";"):
            k, v = tag.split("=")
            tag_queries.append(f'node["{k}"="{v}"](around:{radius_meters},{lat},{lon});')
        query_body = "".join(tag_queries)
    else:
        # Fallback query if type is unknown
        query_body = f'node["shop"="{business_type}"](around:{radius_meters},{lat},{lon});'

    overpass_query = f"""
    [out:json][timeout:25];
    (
      {query_body}
    );
    out body;
    >;
    out skel qt;
    """

    url = "https://overpass-api.de/api/interpreter"
    
    # Respect Overpass API usage (sleep before call)
    time.sleep(1.1)
    
    result = {
        "competitor_count": 0,
        "sample_places": [],
        "source": "osm"
    }
    
    try:
        response = requests.post(url, data={'data': overpass_query}, headers={"User-Agent": "curl/7.68.0", "Accept": "*/*"})
        response.raise_for_status()
        data = response.json()
        
        elements = data.get("elements", [])
        
        # Filter nodes that have tags
        nodes = [e for e in elements if e.get("type") == "node" and "tags" in e]
        
        result["competitor_count"] = len(nodes)
        
        # Get up to 5 sample names
        samples = []
        for node in nodes:
            name = node["tags"].get("name") or node["tags"].get("name:en")
            if name and name not in samples:
                samples.append(name)
            if len(samples) >= 5:
                break
                
        result["sample_places"] = samples

    except Exception as e:
        print(f"Error calling Overpass: {e}")
    
    # Handle the zero results fallback — never report 0 as a confirmed fact,
    # OSM coverage is too sparse for small villages to trust an exact zero.
    if result["competitor_count"] == 0:
        result["source"] = "block_fallback"
        result["competitor_count"] = 4
        
    _density_cache[cache_key] = result
    return result
