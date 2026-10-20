"""Command-line interface for photosearch: try, index, and serve commands."""

import argparse
import time
from pathlib import Path


def cmd_try(args: argparse.Namespace) -> None:
    """Compare a text query against sample photos without using the database.

    Loads the embedding model, encodes the query and images, and displays similarity scores.
    Useful for quick testing and understanding model behavior without indexing.

    Args:
        args: Parsed arguments containing:
            - text: Natural language search query
            - photos: List of image file paths to compare against
    """
    from PIL import Image

    from .embedder import Embedder

    start = time.perf_counter()
    embedder = Embedder()
    print(f"Model loaded in {time.perf_counter() - start:.1f} s\n")

    query = embedder.embed_query(args.text)
    preview = ", ".join(f"{x:.3f}" for x in query[:5])
    print(f"\"{args.text}\" → {len(query)} dimensions: [{preview}, …]\n")

    images = [Image.open(path).convert("RGB") for path in args.photos]
    vectors = embedder.embed_images(images)

    # Normalized vectors: dot product equals cosine similarity
    scores = vectors @ query
    for score, path in sorted(zip(scores, args.photos), reverse=True):
        print(f"  {score:.3f}  {path}")


def cmd_index(args: argparse.Namespace) -> None:
    """Index all photos in a folder and store embeddings in the database.

    Args:
        args: Parsed arguments containing:
            - folder: Directory path containing photos to index
            - data: Directory path for storing database and thumbnails
    """
    from .indexer import index_folder

    index_folder(Path(args.folder), Path(args.data))


def cmd_serve(args: argparse.Namespace) -> None:
    """Start the FastAPI web server for interactive photo search.

    Hosts the web interface at http://127.0.0.1:{port}

    Args:
        args: Parsed arguments containing:
            - data: Directory path where database and thumbnails are stored
            - port: HTTP server port (default: 8000)
    """
    import os

    import uvicorn

    os.environ["PHOTOSEARCH_DATA"] = args.data
    uvicorn.run("photosearch.app:app", host="127.0.0.1", port=args.port)


def main() -> None:
    """Parse command-line arguments and dispatch to the appropriate handler."""
    parser = argparse.ArgumentParser(prog="photosearch")
    parser.add_argument("--data", default="data", help="directory for index and thumbnails")
    commands = parser.add_subparsers(dest="command", required=True)

    try_cmd = commands.add_parser("try", help="compare a text query with sample photos")
    try_cmd.add_argument("text", help="natural language search query")
    try_cmd.add_argument("photos", nargs="+", help="image file paths to compare")
    try_cmd.set_defaults(func=cmd_try)

    index_cmd = commands.add_parser("index", help="index all photos in a folder")
    index_cmd.add_argument("folder", help="directory containing photos")
    index_cmd.set_defaults(func=cmd_index)

    serve_cmd = commands.add_parser("serve", help="start web server at http://127.0.0.1:PORT")
    serve_cmd.add_argument("--port", type=int, default=8000, help="HTTP server port (default: 8000)")
    serve_cmd.set_defaults(func=cmd_serve)

    args = parser.parse_args()
    args.func(args)
