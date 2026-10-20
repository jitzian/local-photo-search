"""Step 4: FastAPI web application for interactive photo search.

Provides REST API endpoints for text search, image search, similarity search ("more like this"),
and photo serving. Includes a static web interface for the browser.
"""

import io
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import db as store
from .embedder import Embedder
from .indexer import load_photo

DATA_DIR = Path(os.environ.get("PHOTOSEARCH_DATA", "data"))
STATIC_DIR = Path(__file__).parent / "static"
(DATA_DIR / "thumbs").mkdir(parents=True, exist_ok=True)

state: dict = {}
model_lock = threading.Lock()  # Ensures only one request uses the model at a time


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and embedding model when the app starts.

    The model is loaded once and reused across all requests.
    Database connection is established and shared in app state.
    """
    state["db"] = store.connect(DATA_DIR / "photos.db")
    state["embedder"] = Embedder()  # Load model once at startup
    yield


app = FastAPI(lifespan=lifespan)


def respond(results: list[dict], start: float) -> dict:
    """Format search results for the API response.

    Adds thumbnail URLs to each result and includes query timing.

    Args:
        results: List of photo dictionaries from search results.
        start: Time when the request started (from time.perf_counter()).

    Returns:
        dict: Response with results and milliseconds elapsed.
    """
    for result in results:
        result["thumb"] = f"/thumbs/{result['id']}.jpg"
    return {"results": results, "ms": round((time.perf_counter() - start) * 1000)}


@app.get("/api/search")
def search(q: str, k: int = 30) -> dict:
    """Search for photos using natural language text query.

    Args:
        q: Natural language search query (e.g., "a dog on the beach").
        k: Maximum number of results to return (default: 30).

    Returns:
        dict: Search results with thumbnail URLs and query time in milliseconds.
    """
    start = time.perf_counter()
    with model_lock:
        vector = state["embedder"].embed_query(q)
    return respond(store.search(state["db"], vector, k), start)


@app.get("/api/similar/{photo_id}")
def similar(photo_id: int, k: int = 30) -> dict:
    """Find photos similar to a specific photo ("more like this").

    Reuses the stored embedding vector; does not invoke the model.

    Args:
        photo_id: ID of the reference photo.
        k: Maximum number of results to return (default: 30).

    Returns:
        dict: Similar photo results (excluding the reference photo itself).

    Raises:
        HTTPException: 404 if photo_id is not found in the database.
    """
    start = time.perf_counter()
    vector = store.get_vector(state["db"], photo_id)  # Already stored: no model needed
    if vector is None:
        raise HTTPException(404, "Photo not found")
    return respond(store.search(state["db"], vector, k, exclude=photo_id), start)


@app.post("/api/search-by-image")
def search_by_image(file: UploadFile, k: int = 30) -> dict:
    """Search for photos by uploading an image file.

    Accepts any format supported by PIL (JPEG, PNG, WEBP, HEIC, etc.).

    Args:
        file: Image file uploaded by the user.
        k: Maximum number of results to return (default: 30).

    Returns:
        dict: Search results based on the uploaded image.
    """
    start = time.perf_counter()
    image, _ = load_photo(io.BytesIO(file.file.read()))
    with model_lock:
        vector = state["embedder"].embed_images([image])[0]
    return respond(store.search(state["db"], vector, k), start)


@app.get("/api/photos")
def latest(limit: int = 60) -> dict:
    """Get the most recently added photos.

    Args:
        limit: Maximum number of photos to return (default: 60).

    Returns:
        dict: Latest photos with thumbnail URLs.
    """
    return respond(store.latest(state["db"], limit), time.perf_counter())


@app.get("/api/photos/{photo_id}/original")
def original(photo_id: int) -> Response:
    """Serve the original photo image file.

    Handles HEIC format by converting to JPEG (browsers don't natively support HEIC).

    Args:
        photo_id: ID of the photo to retrieve.

    Returns:
        Response: The photo image in its native format (or JPEG for HEIC).

    Raises:
        HTTPException: 404 if photo_id is not found in the database.
    """
    photo = store.get_photo(state["db"], photo_id)
    if photo is None:
        raise HTTPException(404, "Photo not found")
    path = Path(photo["path"])
    if path.suffix.lower() != ".heic":
        return FileResponse(path)
    # Convert HEIC to JPEG for browser compatibility
    image, _ = load_photo(path)
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=90)
    return Response(buffer.getvalue(), media_type="image/jpeg")


app.mount("/thumbs", StaticFiles(directory=DATA_DIR / "thumbs"), name="thumbs")
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="web")
