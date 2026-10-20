"""Step 1: Embedding model initialization and inference.

This module manages the EmbeddingGemma 2 multimodal embedding model.
The model runs locally on the user's machine. On first run, it downloads from Hugging Face
(approximately 1.5 GB) and subsequently operates offline.
"""

import numpy as np
import torch
from PIL import Image
from sentence_transformers import SentenceTransformer

MODEL_ID = "google/embeddinggemma-2"

# Matryoshka-style embedding: vectors can be truncated to 512, 256, or 128 dimensions.
# Smaller dimensions reduce storage but require consistent dimensionality across all embeddings.
DIMS = 768

# Vision tokens per image: 70, 140, 280 (default), 560, or 1120.
# Using 70 tokens provides ~8x faster indexing with nearly identical photo search quality.
VISION_TOKENS = 70


def pick_device() -> tuple[str, torch.dtype]:
    """Detect available hardware and select optimal device and precision.
    
    Returns:
        tuple: (device_name, data_type)
            - device_name: "cuda" for NVIDIA GPU, "mps" for Apple Silicon, or "cpu"
            - data_type: torch.bfloat16 where supported, torch.float32 otherwise.
                        Note: float16 is never used as the model does not support it reliably.
    """
    if torch.cuda.is_available():
        return "cuda", torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float32
    if torch.backends.mps.is_available():  # Apple Silicon (Mac M1, M2, etc.)
        return "mps", torch.bfloat16
    return "cpu", torch.float32


class Embedder:
    """Encodes images and text queries into semantic embeddings using EmbeddingGemma 2.
    
    The embedder loads the model once and reuses it across multiple encoding operations.
    Both images and text are projected into a shared 768-dimensional vector space.
    """
    
    def __init__(self) -> None:
        """Initialize the embedding model with optimal device and precision settings.
        
        The audio encoder is disabled to reduce memory footprint from 740M to 440M parameters.
        The model is loaded with the detected device and appropriate data type.
        """
        device, dtype = pick_device()
        self.model = SentenceTransformer(
            MODEL_ID,
            device=device,
            # Text and image only: disabling the audio encoder reduces model parameters from 740M to 440M
            config_kwargs={"audio_config": None},
            model_kwargs={"dtype": dtype},
            processor_kwargs={"max_soft_tokens": VISION_TOKENS},
        )

    def embed_images(self, images: list[Image.Image]) -> np.ndarray:
        """Encode a batch of images into embedding vectors.
        
        Args:
            images: List of PIL Image objects in RGB color space.
            
        Returns:
            np.ndarray: A 2D array of shape (len(images), DIMS) with normalized embeddings.
                       Each row represents one image embedding.
        """
        return self.model.encode(
            images,
            batch_size=16,
            truncate_dim=DIMS,
            normalize_embeddings=True,  # Re-normalize after truncation to maintain unit vectors
        )

    def embed_query(self, text: str) -> np.ndarray:
        """Encode a search query text into an embedding vector.
        
        Uses the SearchQuery prompt template to add the prefix "task: search result | query: "
        to the input text, improving semantic alignment with indexed photo embeddings.
        
        Args:
            text: Natural language search query (e.g., "a dog on the beach").
            
        Returns:
            np.ndarray: A 1D array of length DIMS with the normalized query embedding.
        """
        return self.model.encode(
            text,
            prompt_name="SearchQuery",
            truncate_dim=DIMS,
            normalize_embeddings=True,
        )
