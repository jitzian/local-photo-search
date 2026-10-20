"""Step 2: Database layer with SQLite and vector storage.

This module manages photo metadata and embeddings using SQLite combined with sqlite-vec,
a vector search extension. All data persists in a single local file without requiring
a separate database server.
"""

import sqlite3
from pathlib import Path

import numpy as np
import sqlite_vec

from .embedder import DIMS

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS photos (
    id        INTEGER PRIMARY KEY,
    path      TEXT NOT NULL UNIQUE,
    taken_at  TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS photo_vectors USING vec0(
    photo_id  INTEGER PRIMARY KEY,
    embedding FLOAT[{DIMS}] distance_metric=cosine
);
"""


def connect(path: Path | str) -> sqlite3.Connection:
    """Open or create a SQLite database with vector search support.
    
    Loads the sqlite-vec extension to enable efficient vector operations.
    Initializes the schema with photos and photo_vectors tables on first use.
    
    Args:
        path: File system path to the SQLite database, or ":memory:" for in-memory DB.
        
    Returns:
        sqlite3.Connection: Database connection with sqlite-vec enabled and schema initialized.
    """
    db = sqlite3.connect(path, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.enable_load_extension(True)
    sqlite_vec.load(db)  # Enable vector types and functions in SQLite
    db.enable_load_extension(False)
    db.executescript(SCHEMA)
    return db


def add_photo(db: sqlite3.Connection, path: str, taken_at: str | None, vector: np.ndarray) -> int:
    """Insert a new photo record with its embedding into the database.
    
    Args:
        db: Database connection.
        path: Absolute file path to the photo.
        taken_at: Photo timestamp in ISO 8601 format (e.g., "2026-07-15T18:32:10"), or None.
        vector: Normalized embedding vector of shape (DIMS,).
        
    Returns:
        int: The inserted photo's primary key ID.
    """
    cursor = db.execute("INSERT INTO photos (path, taken_at) VALUES (?, ?)", (path, taken_at))
    db.execute(
        "INSERT INTO photo_vectors (photo_id, embedding) VALUES (?, ?)",
        (cursor.lastrowid, vector.astype(np.float32)),
    )
    return cursor.lastrowid


def search(db: sqlite3.Connection, vector: np.ndarray, k: int = 30, exclude: int | None = None) -> list[dict]:
    """Find the k nearest photos to a query vector using cosine distance.
    
    Performs efficient vector similarity search using sqlite-vec's built-in functions.
    Cosine distance ranges from 0 (identical) to 2 (opposite).
    
    Args:
        db: Database connection.
        vector: Query embedding vector of shape (DIMS,).
        k: Number of results to return (default: 30).
        exclude: Optional photo ID to exclude from results (used for "more like this").
        
    Returns:
        list[dict]: List of up to k photo results, sorted by similarity (closest first).
                   Each dict contains: id, path, taken_at, score (1 - distance).
    """
    rows = db.execute(
        """
        WITH nearest AS (
            SELECT photo_id, distance
            FROM photo_vectors
            WHERE embedding MATCH ? AND k = ?
        )
        SELECT photos.id, photos.path, photos.taken_at, nearest.distance
        FROM nearest
        JOIN photos ON photos.id = nearest.photo_id
        ORDER BY nearest.distance
        """,
        (vector.astype(np.float32), k + 1),
    ).fetchall()
    results = [
        {"id": r["id"], "path": r["path"], "taken_at": r["taken_at"], "score": round(1 - r["distance"], 4)}
        for r in rows
        if r["id"] != exclude
    ]
    return results[:k]


def get_vector(db: sqlite3.Connection, photo_id: int) -> np.ndarray | None:
    """Retrieve the embedding vector for a specific photo.
    
    Args:
        db: Database connection.
        photo_id: The photo's primary key ID.
        
    Returns:
        np.ndarray or None: The embedding vector of shape (DIMS,), or None if not found.
    """
    row = db.execute("SELECT embedding FROM photo_vectors WHERE photo_id = ?", (photo_id,)).fetchone()
    return np.frombuffer(row["embedding"], dtype=np.float32) if row else None


def get_photo(db: sqlite3.Connection, photo_id: int) -> sqlite3.Row | None:
    """Retrieve metadata for a specific photo.
    
    Args:
        db: Database connection.
        photo_id: The photo's primary key ID.
        
    Returns:
        sqlite3.Row or None: Row containing id, path, and taken_at, or None if not found.
    """
    return db.execute("SELECT * FROM photos WHERE id = ?", (photo_id,)).fetchone()


def indexed_paths(db: sqlite3.Connection) -> set[str]:
    """Get the set of all previously indexed photo file paths.
    
    Used during re-indexing to avoid reprocessing already-indexed photos.
    
    Args:
        db: Database connection.
        
    Returns:
        set[str]: Absolute paths of all photos in the database.
    """
    return {row["path"] for row in db.execute("SELECT path FROM photos")}


def latest(db: sqlite3.Connection, limit: int = 60) -> list[dict]:
    """Retrieve the most recent photos, prioritizing those with known timestamps.
    
    Args:
        db: Database connection.
        limit: Maximum number of results to return (default: 60).
        
    Returns:
        list[dict]: Photo records ordered by recency, each containing id, path, and taken_at.
    """
    rows = db.execute(
        "SELECT id, path, taken_at FROM photos ORDER BY taken_at IS NULL, taken_at DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


if __name__ == "__main__":
    # Standalone test: create random vectors and verify search works without loading the full model
    db = connect(":memory:")
    print("sqlite-vec", db.execute("SELECT vec_version()").fetchone()[0])

    rng = np.random.default_rng(0)
    vectors = rng.normal(size=(3, DIMS))
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    for i, vector in enumerate(vectors):
        add_photo(db, f"photo-{i}.jpg", None, vector)

    # Create a query similar to photo 1 and verify it ranks first
    query = vectors[1] + 0.01 * rng.normal(size=DIMS)
    for result in search(db, query / np.linalg.norm(query), k=3):
        print(f"  {result['score']:.3f}  {result['path']}")
