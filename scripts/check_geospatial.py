"""Opt-in live geospatial check; excluded from offline test discovery.

Run: python -m scripts.check_geospatial --live
"""

import argparse


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Allow external OSM requests")
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("Use --live to explicitly enable external API requests.")
    from src.services.datalayer.location_resolver import resolve_location
    from src.services.datalayer.osm_client import get_business_density
    for location in ["Karur, Tamil Nadu", "Bansur, Alwar", "Palakkad, Kerala",
                     "Madhavaram, Andhra Pradesh", "Sonamura, Tripura"]:
        resolved = resolve_location(location)
        print(location, resolved)
        if resolved.get("lat") is not None and resolved.get("lon") is not None:
            density = get_business_density(resolved["lat"], resolved["lon"], "grocery")
            print(density)
            assert get_business_density(resolved["lat"], resolved["lon"], "grocery") is density


if __name__ == "__main__":
    main()
