"""
Embedding Model Module

This module implements the embedding generation for the RAG system.
It uses sentence transformers to create semantic embeddings for
text queries and code snippets.

Author: Umer Farooq, Hussain Waseem Syed, Muhammad Irtaza Khan
Email: umerfarooqcs0891@gmail.com

Purpose:
    - Generate embeddings for natural language queries
    - Generate embeddings for Cirq code snippets
    - Support batch processing for efficiency
    - Leverage PyTorch CUDA for acceleration

Input:
    - Text strings (queries, code, documentation)
    - Batch of texts for batch processing
    - Model configuration parameters

Output:
    - Vector embeddings (typically 384 or 768 dimensions)
    - Embedding metadata
    - Processing statistics

Dependencies:
    - Sentence Transformers: For embedding models
    - PyTorch: For GPU acceleration
    - NumPy: For array operations
    - Transformers (Hugging Face): For model loading

Links to other modules:
    - Used by: Retriever, VectorStore, KnowledgeBase
    - Uses: Sentence Transformers, PyTorch
    - Part of: RAG system pipeline
"""

import json
import os
import time
from typing import List, Union, Optional, Dict, Any
import numpy as np
from pathlib import Path


try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

from ..cirq_rag_code_assistant.config import get_config
from ..cirq_rag_code_assistant.config.logging import get_logger
from ..cirq_rag_code_assistant.bedrock_client import get_bedrock_runtime_client

logger = get_logger(__name__)


class EmbeddingModel:
    """
    Generates semantic embeddings for text and code.

    Supports two providers:
    - local (default): Sentence Transformers, GPU-accelerated, batch processing.
    - aws: Amazon Nova Multimodal Embeddings via Bedrock invoke_model.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        cache_folder: Optional[str] = None,
        provider: Optional[str] = None,
    ):
        """
        Initialize the EmbeddingModel.

        Args:
            model_name: For local: sentence transformer name. For aws: ignored (uses config).
            device: For local: "cpu", "cuda", "auto". Ignored for aws.
            cache_folder: For local: cache folder. Ignored for aws.
            provider: "local" or "aws". Defaults to config models.embedding.provider.
        """
        config = get_config()
        emb_cfg = config.get("models", {}).get("embedding", {})
        aws_cfg = config.get("aws", {})

        self.provider = (provider or emb_cfg.get("provider") or "aws").lower()
        self.model_name = model_name or emb_cfg.get("model_name", "amazon.nova-2-multimodal-embeddings-v1:0")
        self.device = device
        self.cache_folder = cache_folder
        self.model = None
        self._bedrock_client = None

        self.stats = {
            "total_embeddings": 0,
            "total_batches": 0,
            "total_texts": 0,
        }

        if self.provider == "aws":
            self._init_aws(aws_cfg)
        else:
            self._init_local()

    def _init_aws(self, aws_cfg: Dict) -> None:
        """Initialize AWS Bedrock embeddings path."""
        emb_opts = aws_cfg.get("embeddings", {})
        # Avoid hard-coded model IDs; require explicit config when using Bedrock embeddings.
        self._embedding_model_id = emb_opts.get("model_id")
        if not self._embedding_model_id:
            raise ValueError(
                "AWS embeddings provider selected, but aws.embeddings.model_id is not set in config."
            )
        self.embedding_dim = emb_opts.get("embedding_dimension", 1024)
        self._bedrock_client = get_bedrock_runtime_client(read_timeout=60)
        logger.info(f"Using AWS Bedrock Embeddings: {self._embedding_model_id}, dim={self.embedding_dim}")

    def _init_local(self) -> None:
        """Initialize local Sentence Transformer path."""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers is required for local embeddings. "
                "Install it with: pip install sentence-transformers"
            )
        self.device = self._determine_device(self.device)
        logger.info(f"Loading embedding model: {self.model_name}")
        logger.info(f"Using device: {self.device}")
        try:
            self.model = SentenceTransformer(
                self.model_name,
                device=self.device,
                cache_folder=self.cache_folder,
            )
            logger.info("✅ Embedding model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        logger.info(f"Embedding dimension: {self.embedding_dim}")
    
    def _determine_device(self, device: Optional[str] = None) -> str:
        """Determine the device to use for embeddings."""
        if device:
            return device
        
        config = get_config()
        torch_device = config.get("pytorch.torch_device", "auto")
        
        if torch_device == "auto":
            if TORCH_AVAILABLE and torch.cuda.is_available():
                return "cuda"
            return "cpu"
        
        return torch_device
    
    def _encode_single_aws(self, text: str, max_retries: int = 5) -> List[float]:
        """Call Bedrock invoke_model for one text; retry with backoff on ThrottlingException."""
        body = {
            "taskType": "SINGLE_EMBEDDING",
            "singleEmbeddingParams": {
                "embeddingPurpose": "GENERIC_INDEX",
                "embeddingDimension": self.embedding_dim,
                "text": {"truncationMode": "END", "value": text[:8192]},
            },
        }
        last_error = None
        for attempt in range(max_retries):
            try:
                response = self._bedrock_client.invoke_model(
                    modelId=self._embedding_model_id,
                    body=json.dumps(body),
                    contentType="application/json",
                    accept="application/json",
                )
                response_body = json.loads(response["body"].read())
                emb_list = response_body["embeddings"][0]["embedding"]
                return emb_list
            except Exception as e:
                last_error = e
                err_code = None
                if hasattr(e, "response") and isinstance(getattr(e, "response", None), dict):
                    err_code = e.response.get("Error", {}).get("Code")
                is_throttle = err_code == "ThrottlingException" or "Throttling" in type(e).__name__
                if is_throttle and attempt < max_retries - 1:
                    # Long backoff so rate-limit window can reset (Bedrock can be ~10–20 RPM).
                    wait = 15 * (attempt + 1)
                    logger.warning(f"Embedding throttled, waiting {wait}s before retry ({attempt + 1}/{max_retries})")
                    time.sleep(wait)
                else:
                    raise
        raise last_error

    def encode(
        self,
        texts: Union[str, List[str]],
        batch_size: int = 32,
        show_progress_bar: bool = False,
        normalize_embeddings: bool = True,
        convert_to_numpy: bool = True,
    ) -> np.ndarray:
        """
        Generate embeddings for input texts.

        Args:
            texts: Single text string or list of texts
            batch_size: Batch size (local only); for AWS, texts are processed sequentially.
            show_progress_bar: Whether to show progress bar (local only)
            normalize_embeddings: Whether to normalize embeddings to unit length
            convert_to_numpy: Whether to convert to numpy array

        Returns:
            Numpy array of embeddings (shape: [n_texts, embedding_dim])
        """
        if isinstance(texts, str):
            texts = [texts]
        if not texts:
            return np.array([])

        logger.debug(f"Generating embeddings for {len(texts)} texts (provider={self.provider})")

        try:
            if self.provider == "aws":
                # Rate-limit: delay between requests to stay under Bedrock RPM (often low for embeddings).
                # Default 5s ≈ 12 RPM. Increase if still throttled; decrease if your quota is higher.
                delay_seconds = get_config().get("aws", {}).get("embeddings", {}).get("request_delay_seconds", 5.0)
                embeddings_list = []
                for i, t in enumerate(texts):
                    if i > 0:
                        time.sleep(delay_seconds)
                    embeddings_list.append(self._encode_single_aws(t))
                embeddings = np.array(embeddings_list, dtype=np.float32)
                if normalize_embeddings:
                    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
                    norms = np.where(norms == 0, 1, norms)
                    embeddings = embeddings / norms
            else:
                embeddings = self.model.encode(
                    texts,
                    batch_size=batch_size,
                    show_progress_bar=show_progress_bar,
                    normalize_embeddings=normalize_embeddings,
                    convert_to_numpy=convert_to_numpy,
                )

            self.stats["total_embeddings"] += len(texts)
            self.stats["total_batches"] += 1
            self.stats["total_texts"] += len(texts)
            return embeddings
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            if "Unable to locate credentials" in str(e) or type(e).__name__ == "NoCredentialsError":
                raise RuntimeError(
                    "AWS credentials are not configured for Bedrock embeddings. Set "
                    "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in Cirq-RAG-Code-Assistant/.env "
                    "or the project root .env (Docker), or use an IAM role / ~/.aws/credentials. "
                    "If you use Docker Compose, avoid empty AWS_* placeholders in compose—they "
                    "prevent .env from loading. (models.embedding.provider=aws)"
                ) from e
            raise
    
    def encode_queries(self, queries: Union[str, List[str]], **kwargs) -> np.ndarray:
        """
        Generate embeddings for queries (optimized for query encoding).
        
        Args:
            queries: Single query string or list of queries
            **kwargs: Additional arguments passed to encode()
            
        Returns:
            Numpy array of query embeddings
        """
        return self.encode(queries, **kwargs)
    
    def encode_documents(
        self,
        documents: Union[str, List[str]],
        **kwargs
    ) -> np.ndarray:
        """
        Generate embeddings for documents (optimized for document encoding).
        
        Args:
            documents: Single document string or list of documents
            **kwargs: Additional arguments passed to encode()
            
        Returns:
            Numpy array of document embeddings
        """
        return self.encode(documents, **kwargs)
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings produced by this model."""
        return self.embedding_dim
    
    def get_stats(self) -> Dict[str, Any]:
        """Get embedding generation statistics."""
        return self.stats.copy()
    
    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self.stats = {
            "total_embeddings": 0,
            "total_batches": 0,
            "total_texts": 0,
        }
    
    def save_model(self, path: Union[str, Path]) -> None:
        """
        Save the model to disk (local provider only).
        No-op for AWS provider; model lives in Bedrock.
        """
        if self.provider == "aws":
            logger.warning("save_model is a no-op for AWS provider")
            return
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Saving model to {path}")
        self.model.save(str(path))
        logger.info("✅ Model saved successfully")

    @classmethod
    def load_model(cls, path: Union[str, Path], device: Optional[str] = None) -> "EmbeddingModel":
        """
        Load a saved local model from disk. Not supported for AWS provider.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Model path not found: {path}")
        logger.info(f"Loading model from {path}")
        instance = cls.__new__(cls)
        instance.provider = "local"
        instance.model = SentenceTransformer(str(path), device=device)
        instance.embedding_dim = instance.model.get_sentence_embedding_dimension()
        instance.device = device or "cpu"
        instance.model_name = str(path)
        instance.cache_folder = None
        instance._bedrock_client = None
        instance.stats = {
            "total_embeddings": 0,
            "total_batches": 0,
            "total_texts": 0,
        }
        logger.info("✅ Model loaded successfully")
        return instance


def create_embedding_model(
    model_name: Optional[str] = None,
    device: Optional[str] = None,
) -> EmbeddingModel:
    """
    Factory function to create an EmbeddingModel instance.
    
    Args:
        model_name: Name of the embedding model
        device: Device to use
        
    Returns:
        EmbeddingModel instance
    """
    return EmbeddingModel(model_name=model_name, device=device)


# Default embedding model instance (lazy initialization)
_default_model: Optional[EmbeddingModel] = None


def get_default_embedding_model() -> EmbeddingModel:
    """Get or create the default embedding model instance."""
    global _default_model
    
    if _default_model is None:
        _default_model = create_embedding_model()
    
    return _default_model
