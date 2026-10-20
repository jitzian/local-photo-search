# Local Photo Search

Search your photos using natural language ("a dog on the beach", "something for dinner") without uploading anything to the cloud. Uses [EmbeddingGemma 2](https://huggingface.co/google/embeddinggemma-2), Google's open multimodal embedding model, which runs on your machine and stores vectors in SQLite with [sqlite-vec](https://github.com/asg017/sqlite-vec).

```
Index:   photo folder ──▶ EmbeddingGemma 2 ──▶ vector (768 numbers) ──▶ SQLite + sqlite-vec
Search:  "a dog"       ──▶ EmbeddingGemma 2 ──▶ vector ──▶ nearest neighbors ──▶ photos
```

Text and images fall into the same vector space, so a phrase and a photo about the same thing end up close to each other.

A step-by-step explanation is available in [this video](https://www.youtube.com/watch?v=ZLP-49T5gW4).

## Requirements

- [uv](https://docs.astral.sh/uv/) — Python package manager
- ~2 GB free disk space for the model (downloaded on first run)
- Mac with Apple Silicon, NVIDIA GPU, or CPU (slower)

## Quick Start

### Automated Setup (Recommended)

The easiest way to get started is using the provided shell script:

```bash
# Make the script executable
chmod +x run.sh

# Download sample photos and start the server
./run.sh setup

# Now open http://127.0.0.1:8000 in your browser
```

### Manual Setup

If you prefer manual control:

```bash
# Install dependencies
uv sync

# Download 400 sample Unsplash photos for testing
uv run scripts/download_sample_photos.py

# Index the sample photos
uv run photosearch index sample-photos

# Start the web server
uv run photosearch serve
```

Open your browser to **http://127.0.0.1:8000** and start searching!

## Usage

### Using the Web Interface

- **Text search**: Type what you're looking for ("a sunset", "people laughing")
- **More like this**: Click any photo to see similar photos
- **Image search**: Drag an image from your desktop onto the search area

### Using the Command Line

```bash
# Compare a text query with sample photos (no database needed)
./run.sh try "a dog on the beach" sample-photos/unsplash-237.jpg sample-photos/unsplash-10.jpg

# Index your own photo folder
./run.sh index ~/Pictures

# Start the server
./run.sh serve

# Clean up and re-download everything
./run.sh clean
```

### Command-line options

```bash
./run.sh --help          # Show all available commands
./run.sh setup           # Download samples, index, and start server
./run.sh download [N]    # Download N sample photos (default: 400)
./run.sh index <folder>  # Index photos from a folder
./run.sh serve [PORT]    # Start web server (default port: 8000)
./run.sh clean           # Delete sample photos and database, then re-download
./run.sh try <query> <photos>...  # Quick test without database
```

## Architecture: Step by Step

Each step has its own tag (`git checkout paso-1`) and can be run independently.

| Step | File | What It Does |
|---|---|---|
| 1 | [`embedder.py`](src/photosearch/embedder.py) | Loads the model and converts photos and text to vectors. Test with: `./run.sh try "a dog" sample-photos/unsplash-237.jpg sample-photos/unsplash-10.jpg` |
| 2 | [`db.py`](src/photosearch/db.py) | `photos` table, `photo_vectors` table, and SQL-based neighbor search. Test with: `uv run python -m photosearch.db` |
| 3 | [`indexer.py`](src/photosearch/indexer.py) | Walks a folder, computes vectors in batches, and saves thumbnails |
| 4 | [`app.py`](src/photosearch/app.py) and [`static/`](src/photosearch/static) | FastAPI backend and web interface |

## Configuration

In [`embedder.py`](src/photosearch/embedder.py), you can tune these parameters:

- **`VISION_TOKENS`**: Default 70 per image; the model uses 280 by default. Fewer tokens = faster indexing. For photos, 70 gives nearly identical results.
- **`DIMS`**: 768 (default). Thanks to Matryoshka, you can truncate to 512, 256, or 128 dimensions to save space. **Important**: Re-index if you change this—queries and photos must use the same size.
- **Precision**: `bfloat16` on GPU, `float32` on CPU. Google advises against `float16` with this model.

### Important Details

- Text queries use the prompt `task: search result | query: ` (added automatically by the model).
- Image processing requires both `sentence-transformers` and `torchvision`.
- **Do not mix vectors from different models.** If you switch models, re-index everything.

## Performance

On a MacBook Pro M3 Pro with bfloat16 and 70 tokens per image:

| Operation | Speed |
|---|---|
| Index | ~26 photos/s (for 1200×800 samples, including JPEG decode and thumbnail generation) |
| Text search | ~25 ms |
| "More like this" | ~1 ms (reuses stored vector, no model invocation) |
| GPU memory | ~1.6 GB |

**Baseline**: Default model settings (float32 and 280 tokens) indexes at 3.6 photos/s.

## Limitations

- **No counting**: "three people" might return results with three forks.
- **Negations confuse it**: "beach without people" might include beaches with people.
- **Always returns results**: The similarity scores cluster tightly (0.60–0.75), so rank order and spread matter more than absolute scores.

## Credits

Sample photos are from [Unsplash](https://unsplash.com/license) and downloaded via [Lorem Picsum](https://picsum.photos).

## License

Code is licensed under [MIT](LICENSE). Sample photos are not part of the repository and retain their Unsplash license.
