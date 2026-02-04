#!/usr/bin/env python3
"""
Convert KMGI Roku Direct Publisher feed to Roku Search Feed format.

Roku Search Feed spec:
https://developer.roku.com/docs/specs/search/search-feed.md

Key differences from Direct Publisher:
- Root: version, defaultLanguage, defaultAvailabilityCountries, assets[]
- Titles/descriptions are arrays of {value, languages}
- Images use type "main" or "background" (not "thumbnail")
- Rating uses advisoryRatings[] with {source, value}
- Content uses playOptions[] with {license, quality, playId}
- Country codes are lowercase
"""

import json
import sys

# Valid Roku Search Feed genres (from spec)
VALID_GENRES = {
    "action", "action sports", "adventure", "aerobics", "agriculture", "animals",
    "animated", "anime", "anthology", "archery", "arm wrestling", "art", "arts/crafts",
    "artistic gymnastics", "artistic swimming", "athletics", "auction", "auto",
    "auto racing", "aviation", "awards", "badminton", "ballet", "baseball",
    "basketball", "3x3 basketball", "beach soccer", "beach volleyball", "biathlon",
    "bicycle", "bicycle racing", "billiards", "biography", "blackjack", "bmx racing",
    "boat", "boat racing", "bobsled", "bodybuilding", "bowling", "boxing",
    "bullfighting", "bus./financial", "canoe", "card games", "ceremony", "cheerleading",
    "children", "children-music", "children-special", "children-talk", "collectibles",
    "comedy", "comedy drama", "community", "computers", "canoe/kayak", "consumer",
    "cooking", "cricket", "crime", "crime drama", "curling", "cycling", "dance",
    "dark comedy", "darts", "debate", "diving", "docudrama", "documentary",
    "dog racing", "dog show", "dog sled", "drag racing", "drama", "educational",
    "entertainment", "environment", "equestrian", "erotic", "event", "exercise",
    "fantasy", "faith", "fashion", "fencing", "field hockey", "figure skating",
    "fishing", "football", "food", "fundraiser", "gaelic football", "game show",
    "gaming", "gay/lesbian", "golf", "gymnastics", "handball", "health",
    "historical drama", "history", "hockey", "holiday", "holiday music",
    "holiday music special", "holiday special", "holiday-children",
    "holiday-children special", "home improvement", "horror", "horse", "house/garden",
    "how-to", "hunting", "hurling", "hydroplane racing", "indoor soccer", "interview",
    "intl soccer", "judo", "karate", "kayaking", "lacrosse", "law", "live", "luge",
    "martial arts", "medical", "military", "miniseries", "mixed martial arts",
    "modern pentathlon", "motorcycle", "motorcycle racing", "motorsports",
    "mountain biking", "music", "music special", "music talk", "musical",
    "musical comedy", "mystery", "nature", "news", "newsmagazine", "olympics",
    "opera", "outdoors", "parade", "paranormal", "parenting", "performing arts",
    "playoff sports", "poker", "politics", "polo", "pool", "pro wrestling",
    "public affairs", "racquet", "reality", "religious", "ringuette", "road cycling",
    "rodeo", "roller derby", "romance", "romantic comedy", "rowing", "rugby",
    "running", "rhythmic gymnastics", "sailing", "science", "science fiction",
    "self improvement", "shooting", "shopping", "sitcom", "skateboarding", "skating",
    "skeleton", "skiing", "snooker", "snowboarding", "snowmobile", "soap",
    "soap special", "soap talk", "soccer", "softball", "special", "speed skating",
    "sport climbing", "sports", "sports talk", "squash", "standup", "sumo wrestling",
    "surfing", "suspense", "swimming", "table tennis", "taekwondo", "talk",
    "technology", "tennis", "theater", "thriller", "track/field", "track cycling",
    "travel", "trampoline", "triathlon", "variety", "volleyball", "war", "water polo",
    "water skiing", "watersports", "weather", "weightlifting", "western", "wrestling",
    "yacht racing"
}


def truncate(text, max_len):
    """Truncate text to max_len characters."""
    if not text:
        return text
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def validate_genres(genres):
    """Return only valid genres; default to ['special'] if none valid."""
    valid = [g for g in genres if g.lower() in VALID_GENRES]
    # Return lowercase to match spec
    if not valid:
        return ["special"]
    return [g.lower() for g in valid]


def convert_item(item, item_type):
    """Convert a Direct Publisher item to Search Feed asset."""
    title = truncate(item.get("title", "Untitled"), 200)
    short_desc = truncate(item.get("shortDescription", title), 200)
    long_desc = truncate(item.get("longDescription", ""), 500)

    asset = {
        "id": item["id"][:50],  # Max 50 chars
        "type": item_type,
        "titles": [{"value": title, "languages": ["en"]}],
        "shortDescriptions": [{"value": short_desc, "languages": ["en"]}],
        "releaseDate": item.get("releaseDate", "2025-01-01"),
        "genres": validate_genres(item.get("genres", ["special"])),
        "advisoryRatings": [],
        "images": [],
        "content": {
            "playOptions": []
        }
    }

    # Long description (optional, only if non-empty)
    if long_desc:
        asset["longDescriptions"] = [{"value": long_desc, "languages": ["en"]}]

    # Rating conversion: Direct Publisher → Search Feed
    rating = item.get("rating", {})
    if rating:
        # Map rating source
        source_map = {
            "USA_TV": "USA_PR",
            "MPAA": "MPAA",
            "USA_PR": "USA_PR"
        }
        source = source_map.get(rating.get("ratingSource", "USA_TV"), "USA_PR")

        # Map rating value (spec accepts both "TV-G" and "TVG" forms)
        value = rating.get("rating", "TV-G")
        asset["advisoryRatings"] = [{"source": source, "value": value}]
    else:
        # Default rating required
        asset["advisoryRatings"] = [{"source": "USA_PR", "value": "TV-G"}]

    # Thumbnail → image with type "main" (spec requires "main" or "background")
    if item.get("thumbnail"):
        asset["images"] = [{"type": "main", "url": item["thumbnail"]}]

    # Content/videos → playOptions
    content = item.get("content", {})
    if content.get("videos"):
        for vid in content["videos"]:
            quality_map = {
                "HD": "hd",
                "SD": "sd",
                "UHD": "uhd",
                "FHD": "fhd"
            }
            play_option = {
                "license": "free",
                "quality": quality_map.get(vid.get("quality", "HD").upper(), "hd")
            }
            # Extract playId from proxy URL
            url = vid.get("url", "")
            if "/play/" in url:
                play_id = url.split("/play/")[-1]
                play_option["playId"] = play_id
            else:
                play_option["playId"] = item["id"]
            asset["content"]["playOptions"].append(play_option)

    # Ensure at least one playOption exists
    if not asset["content"]["playOptions"]:
        asset["content"]["playOptions"] = [{
            "license": "free",
            "quality": "hd",
            "playId": item["id"]
        }]

    # Duration (required for non-series/season)
    if content.get("duration"):
        asset["durationInSeconds"] = content["duration"]
    else:
        # Default 60 seconds if missing
        asset["durationInSeconds"] = 60

    # Tags (each max 20 chars)
    if item.get("tags"):
        clean_tags = [t.strip('"').strip()[:20] for t in item["tags"] if t.strip('"').strip()]
        if clean_tags:
            asset["tags"] = clean_tags

    return asset


def main():
    input_file = "roku_feed.json"
    output_file = "roku_search_feed.json"

    with open(input_file, "r") as f:
        dp_feed = json.load(f)

    print(f"Provider: {dp_feed.get('providerName', 'Unknown')}")
    movies = dp_feed.get("movies", [])
    shortforms = dp_feed.get("shortFormVideos", [])
    print(f"Movies: {len(movies)}")
    print(f"Short Form Videos: {len(shortforms)}")

    assets = []
    errors = 0

    # Convert movies
    for movie in movies:
        try:
            assets.append(convert_item(movie, "movie"))
        except Exception as e:
            print(f"  ERROR movie {movie.get('id', '?')}: {e}", file=sys.stderr)
            errors += 1

    # Convert short form videos
    for sf in shortforms:
        try:
            assets.append(convert_item(sf, "shortform"))
        except Exception as e:
            print(f"  ERROR shortform {sf.get('id', '?')}: {e}", file=sys.stderr)
            errors += 1

    # Build search feed with lowercase country codes per spec
    search_feed = {
        "version": "1",
        "defaultLanguage": "en",
        "defaultAvailabilityCountries": ["us"],
        "assets": assets
    }

    with open(output_file, "w") as f:
        json.dump(search_feed, f, indent=2)

    file_size = len(json.dumps(search_feed))
    print(f"\nSearch feed written to {output_file}")
    print(f"Total assets: {len(assets)}")
    print(f"Errors: {errors}")
    print(f"File size: {file_size / 1024 / 1024:.1f} MB")

    # Validation checks
    print("\n--- Validation ---")
    id_set = set()
    dupes = 0
    missing_images = 0
    missing_duration = 0
    long_titles = 0
    long_short_desc = 0

    for a in assets:
        if a["id"] in id_set:
            dupes += 1
        id_set.add(a["id"])
        if not a.get("images"):
            missing_images += 1
        if not a.get("durationInSeconds"):
            missing_duration += 1
        for t in a.get("titles", []):
            if len(t["value"]) > 200:
                long_titles += 1
        for d in a.get("shortDescriptions", []):
            if len(d["value"]) > 200:
                long_short_desc += 1

    print(f"Duplicate IDs: {dupes}")
    print(f"Missing images: {missing_images}")
    print(f"Missing duration: {missing_duration}")
    print(f"Titles > 200 chars: {long_titles}")
    print(f"Short descs > 200 chars: {long_short_desc}")

    # Print samples
    print("\n--- Sample Movie ---")
    movie_assets = [a for a in assets if a["type"] == "movie"]
    if movie_assets:
        print(json.dumps(movie_assets[0], indent=2))

    print("\n--- Sample Shortform ---")
    sf_assets = [a for a in assets if a["type"] == "shortform"]
    if sf_assets:
        print(json.dumps(sf_assets[0], indent=2))


if __name__ == "__main__":
    main()
