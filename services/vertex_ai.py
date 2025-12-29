"""
Hugo - Inbox Watchdog Agent
Vertex AI Service

Centralized Google Cloud + Vertex AI integration.
Provides helper functions for text generation and embeddings.

Setup:
1. Install: pip install google-cloud-aiplatform
2. Authenticate: gcloud auth application-default login
3. Set env vars: GCP_PROJECT_ID, GCP_LOCATION
"""

import logging
import os
from typing import Optional

import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
from vertexai.language_models import TextEmbeddingModel, TextEmbeddingInput

from config.settings import settings

# Configure logger
logger = logging.getLogger("hugo.vertex_ai")

# Module-level state for lazy initialization
_initialized: bool = False
_text_model: Optional[GenerativeModel] = None
_embedding_model: Optional[TextEmbeddingModel] = None


def _ensure_initialized() -> None:
    """
    Initialize Vertex AI SDK with project settings.
    Uses application-default credentials (gcloud auth).
    Called lazily on first API call.
    """
    global _initialized, _text_model, _embedding_model
    
    if _initialized:
        return
    
    # Guard: Skip initialization if Vertex AI is disabled
    use_vertex_ai = os.environ.get("USE_VERTEX_AI", "").lower()
    if use_vertex_ai != "true":
        raise RuntimeError("Vertex AI disabled")
    
    try:
        # Initialize Vertex AI with project and location from env
        vertexai.init(
            project=settings.GCP_PROJECT_ID,
            location=settings.GCP_LOCATION
        )
        
        # Initialize Gemini Pro for text generation
        _text_model = GenerativeModel(settings.GEMINI_MODEL)
        logger.info(f"Initialized text model: {settings.GEMINI_MODEL}")
        
        # Initialize embedding model
        _embedding_model = TextEmbeddingModel.from_pretrained(settings.EMBEDDING_MODEL)
        logger.info(f"Initialized embedding model: {settings.EMBEDDING_MODEL}")
        
        _initialized = True
        logger.info(f"Vertex AI ready (project: {settings.GCP_PROJECT_ID}, location: {settings.GCP_LOCATION})")
        
    except Exception as e:
        logger.error(f"Failed to initialize Vertex AI: {e}")
        raise RuntimeError(f"Vertex AI initialization failed: {e}")


def generate_text(
    prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    json_mode: bool = False
) -> str:
    """
    Generate text using Gemini Pro.
    
    Args:
        prompt: Input prompt for the model
        temperature: Sampling temperature (0.0-1.0), lower = more deterministic
        max_tokens: Maximum output tokens
        json_mode: If True, request JSON response format
    
    Returns:
        Generated text response
    
    Raises:
        RuntimeError: If Vertex AI is not properly configured
    
    Example:
        >>> response = generate_text("Summarize this email: ...")
        >>> print(response)
    """
    _ensure_initialized()
    
    if not _text_model:
        raise RuntimeError("Text model not initialized")
    
    # Configure generation parameters
    config = GenerationConfig(
        temperature=temperature,
        max_output_tokens=max_tokens,
    )
    
    # Enable JSON mode if requested
    if json_mode:
        config = GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json"
        )
    
    logger.debug(f"Generating text (temp={temperature}, max_tokens={max_tokens})")
    
    # Generate response
    response = _text_model.generate_content(prompt, generation_config=config)
    
    return response.text


def generate_embedding(text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    """
    Generate text embedding using Vertex AI embedding model.
    
    Args:
        text: Input text to embed
        task_type: Embedding task type for optimization:
            - "RETRIEVAL_DOCUMENT": For documents to be searched
            - "RETRIEVAL_QUERY": For search queries
            - "SEMANTIC_SIMILARITY": For comparing text similarity
            - "CLASSIFICATION": For text classification
            - "CLUSTERING": For text clustering
    
    Returns:
        List of floats representing the embedding vector (768 dimensions)
    
    Example:
        >>> embedding = generate_embedding("Delivery delayed by 7 days")
        >>> len(embedding)
        768
    """
    _ensure_initialized()
    
    if not _embedding_model:
        raise RuntimeError("Embedding model not initialized")
    
    logger.debug(f"Generating embedding for text ({len(text)} chars)")
    
    # Create embedding input with task type
    embedding_input = TextEmbeddingInput(text=text, task_type=task_type)
    
    # Generate embedding
    embeddings = _embedding_model.get_embeddings([embedding_input])
    
    # Return the embedding values
    return embeddings[0].values


def generate_embeddings_batch(
    texts: list[str], 
    task_type: str = "RETRIEVAL_DOCUMENT"
) -> list[list[float]]:
    """
    Generate embeddings for multiple texts in a single API call.
    More efficient than calling generate_embedding in a loop.
    
    Args:
        texts: List of texts to embed
        task_type: Embedding task type (see generate_embedding)
    
    Returns:
        List of embedding vectors
    
    Example:
        >>> embeddings = generate_embeddings_batch(["text1", "text2"])
        >>> len(embeddings)
        2
    """
    _ensure_initialized()
    
    if not _embedding_model:
        raise RuntimeError("Embedding model not initialized")
    
    logger.debug(f"Generating embeddings for {len(texts)} texts")
    
    # Create embedding inputs
    inputs = [TextEmbeddingInput(text=t, task_type=task_type) for t in texts]
    
    # Generate embeddings in batch
    embeddings = _embedding_model.get_embeddings(inputs)
    
    return [e.values for e in embeddings]


def is_available() -> bool:
    """
    Check if Vertex AI is properly configured and available.
    
    Returns:
        True if Vertex AI is ready to use
    """
    try:
        _ensure_initialized()
        return _initialized and _text_model is not None and _embedding_model is not None
    except Exception:
        return False


# Optional: Re-export for convenience
__all__ = [
    "generate_text",
    "generate_embedding",
    "generate_embeddings_batch",
    "is_available",
]
