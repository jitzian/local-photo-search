"""Step 3: Indexing pipeline that processes photos and stores their embeddings.

This module recursively walks a directory tree, loads images, computes embeddings in batches,
generates thumbnails, and stores results in the database. It skips already-indexed photos
for efficiency on re-runs.
"""

import time
from pathlib import Path
from typing import BinaryIO

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

from . import db as store
from .embedder import Embedder

register_heif_opener()  # Enable support for .heic format (iPhone and Google Photos exports)

EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
BATCH_SIZE = 16
THUMB_SIZE = 512
EXIF_IFD = 0x8769
DATE_TAKEN = 36867  # EXIF tag: DateTimeOriginal


def find_photos(folder: Path) -> list[Path]:
    """Recursively locate all supported image files in a directory.

    Args:
        folder: Root directory to search.

    Returns:
        list[Path]: Sorted list of paths to supported image files.
    """
    return sorted(path for path in folder.rglob("*") if path.suffix.lower() in EXTENSIONS)


def load_photo(source: Path | BinaryIO) -> tuple[Image.Image, str | None]:
    """Load and prepare an image for embedding.

    - Decodes JPEG at reduced size for speed (1024x1024 preview).
    - Extracts EXIF metadata to recover original capture timestamp.
    - Applies EXIF orientation to correct mobile photo rotations.
    - Converts all images to RGB color space.

    Args:
        source: File path or file-like object containing image data.

    Returns:
        tuple: (image, taken_at)
            - image: PIL Image in RGB mode, ready for embedding.
            - taken_at: ISO 8601 timestamp string (e.g., "2026-07-15T18:32:10"), or None.
    """
    image = Image.open(source)
    image.draft("RGB", (1024, 1024))  # For JPEG: decode at reduced resolution (much faster)
    taken_at = image.getexif().get_ifd(EXIF_IFD).get(DATE_TAKEN)  # Format: "2026:07:15 18:32:10"
    if taken_at:
        # Convert EXIF datetime format to ISO 8601
        taken_at = taken_at.replace(":", "-", 2).replace(" ", "T")
    image = ImageOps.exif_transpose(image).convert("RGB")  # Correct orientation, ensure RGB
    return image, taken_at


def index_folder(folder: Path, data_dir: Path) -> None:
    """Index all photos in a folder: compute embeddings, store vectors, and generate thumbnails.

    This function processes photos in batches for efficiency. It skips photos already in
    the database and reports progress as it works. Thumbnails are saved to data_dir/thumbs/
    with filenames matching their database IDs.

    Args:
        folder: Directory containing photos to index.
        data_dir: Directory where to store database and thumbnails.
    """
    thumbs = data_dir / "thumbs"
    thumbs.mkdir(parents=True, exist_ok=True)
    db = store.connect(data_dir / "photos.db")

    already_indexed = store.indexed_paths(db)
    pending = [path for path in find_photos(folder) if str(path.resolve()) not in already_indexed]
    print(f"{len(pending)} new photos in {folder}")
    if not pending:
        return

    embedder = Embedder()
    start = time.perf_counter()
    for i in range(0, len(pending), BATCH_SIZE):
        photos = []
        for path in pending[i : i + BATCH_SIZE]:
            try:
                photos.append((path, *load_photo(path)))
            except Exception as error:  # Corrupted file or unsupported format
                print(f"\n  Skipping {path.name}: {error}")
        if not photos:
            continue

        # Compute embeddings in batch
        vectors = embedder.embed_images([image for _, image, _ in photos])

        # Store each photo and generate thumbnail
        for (path, image, taken_at), vector in zip(photos, vectors):
            photo_id = store.add_photo(db, str(path.resolve()), taken_at, vector)
            image.thumbnail((THUMB_SIZE, THUMB_SIZE))
            image.save(thumbs / f"{photo_id}.jpg", quality=85)
        db.commit()

        done = min(i + BATCH_SIZE, len(pending))
        print(f"\r  {done}/{len(pending)} · {done / (time.perf_counter() - start):.1f} photos/s", end="", flush=True)
    print()
