import torch
import logging
from sentence_transformers import CrossEncoder

from app.config import RERANKER_MODEL_NAME, RERANKER_DEVICE

logger = logging.getLogger(__name__)

class RerankerService:
    def __init__(
        self,
        model_name: str = RERANKER_MODEL_NAME,
        device: str = RERANKER_DEVICE,
    ):
        resolved_device = self._resolve_device(device)

        self.model = CrossEncoder(
            model_name,
            device=resolved_device,
        )

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"

        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError(
                "RERANKER_DEVICE is set to 'cuda', "
                "but CUDA is not available."
            )

        if device not in {"cuda", "cpu"}:
            raise ValueError(
                "RERANKER_DEVICE must be 'auto', 'cuda', or 'cpu'."
            )

        return device

    def rerank(
        self,
        query: str,
        documents: list[dict],
        top_k: int = 3,
    ) -> list[dict]:
        if not query.strip():
            raise ValueError("Query cannot be empty")

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")

        if not documents:
            return []

        pairs = [
            (query, document["text"])
            for document in documents
        ]

        try:
            scores = self.model.predict(
                pairs,
                batch_size=8,
                show_progress_bar=False,
            )
        except Exception:
            logger.exception(
                "Reranker inference failed",
                extra={
                    "document_count": len(documents),
                    "device": str(self.model.model.device),
                },
            )
            raise

        if len(scores) != len(documents):
            raise RuntimeError(
                "Reranker returned a different number of scores "
                "than input documents."
            )

        ranked_documents = []

        for document, score in zip(documents, scores):
            ranked_documents.append(
                {
                    **document,
                    "rerank_score": float(score),
                }
            )

        ranked_documents.sort(
            key=lambda item: item["rerank_score"],
            reverse=True,
        )

        return ranked_documents[:top_k]