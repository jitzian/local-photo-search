"""Download sample photos from Unsplash (via picsum.photos) for testing.

Usage:
    uv run scripts/download_sample_photos.py        # Download 400 sample photos to sample-photos/
    uv run scripts/download_sample_photos.py 100    # Download only 100 photos
"""

import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

OUT = Path("sample-photos")
COUNT = int(sys.argv[1]) if len(sys.argv) > 1 else 400


def photo_ids(count: int) -> list[str]:
    """Fetch a list of Unsplash photo IDs from the picsum.photos API.
    
    Args:
        count: Number of photo IDs to retrieve.
        
    Returns:
        list[str]: List of photo ID strings.
    """
    ids: list[str] = []
    page = 1
    while len(ids) < count:
        with urllib.request.urlopen(f"https://picsum.photos/v2/list?page={page}&limit=100") as response:
            items = json.load(response)
        if not items:
            break
        ids += [item["id"] for item in items]
        page += 1
    return ids[:count]


def download(photo_id: str) -> None:
    """Download a single photo from picsum.photos if not already present.
    
    Args:
        photo_id: Unsplash photo ID string.
    """
    dest = OUT / f"unsplash-{photo_id}.jpg"
    if not dest.exists():
        urllib.request.urlretrieve(f"https://picsum.photos/id/{photo_id}/1200/800.jpg", dest)


OUT.mkdir(exist_ok=True)
print(f"Downloading {COUNT} sample photos from Unsplash (via picsum.photos)...")
with ThreadPoolExecutor(max_workers=12) as pool:
    list(pool.map(download, photo_ids(COUNT)))
total = len(list(OUT.glob('*.jpg')))
print(f"✓ {total} photos downloaded to {OUT}/")
