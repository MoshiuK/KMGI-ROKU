#!/usr/bin/env python3
"""
Convert the Direct Publisher format feed to Roku Search Feed format.

Roku Search Feed spec: https://developer.roku.com/docs/specs/search/search-feed.md

Root: { version, defaultLanguage, defaultAvailabilityCountries, assets[] }
Asset: { id, type, titles[], shortDescriptions[], longDescriptions[], releaseDate,
         genres[], tags[], images[], durationInSeconds, content.playOptions[], advisoryRatings[] }
"""

import json
import sys
import re

# Valid Roku genres (lowercase for matching)
VALID_GENRES = {
    "action", "action sports", "adventure", "aerobics", "agriculture", "animals",
    "animated", "anime", "anthology", "archery", "arm wrestling", "art", "arts/crafts",
    "artistic gymnastics", "artistic swimming", "athletics", "auction", "auto",
    "auto racing", "aviation", "awards", "badminton", "ballet", "baseball",
    "basketball", "3x3 basketball", "beach soccer", "beach volleyball", "biathlon",
    "bicycle", "bicycle racing", "billiards", "biography", "blackjack", "bmx racing",
    "boat", "boat racing", "bobsled", "bodybuilding", "bowling", "boxing",
    "bullfighting", "bus./financial", "canoe", "card games", "ceremony",
    "cheerleading", "children", "children-music", "children-special", "children-talk",
    "collectibles", "comedy", "comedy drama", "community", "computers", "canoe/kayak",
    "consumer", "cooking", "cricket", "crime", "crime drama", "curling", "cycling",
    "dance", "dark comedy", "darts", "debate", "diving", "docudrama", "documentary",
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
    "travel", "trampoline", "triathlon", "variety", "volleyball", "war",
    "water polo", "water skiing", "watersports", "weather", "weightlifting",
    "western", "wrestling", "yacht racing"
}


def classify_content(title, description, tags, duration_secs):
    """Try to assign a valid Roku genre based on content analysis."""
    text = f"{title} {description} {' '.join(tags)}".lower()
    
    # Church/religious content
    if any(w in text for w in ['church', 'sermon', 'bible', 'pastor', 'worship', 'prayer', 
                                'gospel', 'praise', 'ministry', 'missionary', 'baptist',
                                'pastoral', 'deacon', 'sunday', 'galilee', 'scripture',
                                'christmas eve', 'easter', 'revival']):
        return ["faith"]
    
    # Music content
    if any(w in text for w in ['music', 'song', 'concert', 'singing', 'choir', 'hymn']):
        return ["music"]
    
    # Holiday content
    if any(w in text for w in ['christmas', 'holiday', 'thanksgiving', 'easter']):
        return ["holiday"]
    
    # News/talk
    if any(w in text for w in ['news', 'interview', 'talk', 'discussion']):
        return ["talk"]
    
    # Community
    if any(w in text for w in ['community', 'neighborhood', 'local', 'event']):
        return ["community"]
    
    # Educational
    if any(w in text for w in ['education', 'learn', 'class', 'lesson', 'tutorial']):
        return ["educational"]
    
    # Default for religious org content
    return ["faith"]


def convert_item(item, item_type):
    """Convert a Direct Publisher item to Search Feed asset format."""
    
    # Extract video ID from proxy URL for playId
    video_url = ""
    play_id = item["id"]
    if "content" in item and "videos" in item["content"] and item["content"]["videos"]:
        video_url = item["content"]["videos"][0].get("url", "")
        # Extract vimeo ID from proxy URL
        match = re.search(r'/play/(\d+)', video_url)
        if match:
            play_id = match.group(1)
    
    # Duration
    duration = item.get("content", {}).get("duration", 0)
    if duration is None or duration == 0:
        duration = 1  # Minimum 1 second to avoid validation failure
    
    # Determine type
    if item_type == "shortform":
        asset_type = "shortform"
    else:
        # Movies are >15 min content
        if duration > 900:  # 15 min in seconds
            asset_type = "movie"
        else:
            asset_type = "shortform"
    
    # Title (max 200 chars)
    title = (item.get("title", "") or "Untitled")[:200]
    
    # Short description (max 200 chars)
    short_desc = (item.get("shortDescription", "") or title)[:200]
    
    # Long description (max 500 chars)
    long_desc = (item.get("longDescription", "") or short_desc)[:500]
    
    # Genres - must be from Roku's approved list
    genres = classify_content(title, short_desc, item.get("tags", []), duration)
    
    # Tags (max 20 chars each)
    tags = [t[:20] for t in item.get("tags", []) if t and len(t.strip()) > 0]
    
    # Thumbnail as main image
    thumbnail = item.get("thumbnail", "")
    images = []
    if thumbnail:
        images.append({
            "type": "main",
            "url": thumbnail
        })
    
    asset = {
        "id": item["id"],
        "type": asset_type,
        "titles": [{"value": title}],
        "shortDescriptions": [{"value": short_desc}],
        "longDescriptions": [{"value": long_desc}],
        "releaseDate": item.get("releaseDate", "2025-01-01"),
        "genres": genres,
        "tags": tags if tags else ["faith"],
        "advisoryRatings": [
            {
                "source": "USA_PR",
                "value": "TV-G"
            }
        ],
        "images": images,
        "durationInSeconds": duration,
        "content": {
            "playOptions": [
                {
                    "license": "free",
                    "quality": "hd",
                    "playId": play_id
                }
            ]
        }
    }
    
    return asset


def main():
    input_file = "roku_feed.json"
    output_file = "roku_feed.json"
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    print(f"Reading {input_file}...")
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    assets = []
    
    # Convert movies
    movies = data.get("movies", [])
    print(f"Converting {len(movies)} movies...")
    for item in movies:
        asset = convert_item(item, "movie")
        assets.append(asset)
    
    # Convert short form videos
    shorts = data.get("shortFormVideos", [])
    print(f"Converting {len(shorts)} short form videos...")
    for item in shorts:
        asset = convert_item(item, "shortform")
        assets.append(asset)
    
    # Build Search Feed
    search_feed = {
        "version": "1",
        "defaultLanguage": "en",
        "defaultAvailabilityCountries": ["us"],
        "assets": assets
    }
    
    print(f"Total assets: {len(assets)}")
    print(f"Writing {output_file}...")
    
    with open(output_file, 'w') as f:
        json.dump(search_feed, f, indent=2)
    
    size = len(json.dumps(search_feed))
    print(f"Feed size: {size:,} bytes ({size/1024/1024:.1f} MB)")
    print("Done!")


if __name__ == "__main__":
    main()
