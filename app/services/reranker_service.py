import torch
from sentence_transformers import CrossEncoder

from app.config import RERANKER_MODEL_NAME, RERANKER_DEVICE


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

        if not documents:
            return []

        pairs = [
            (query, document["text"])
            for document in documents
        ]

        scores = self.model.predict(
            pairs,
            batch_size=8,
            show_progress_bar=False,
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