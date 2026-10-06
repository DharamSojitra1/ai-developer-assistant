import chromadb


class VectorStoreService:
    def __init__(
        self,
        persist_directory: str = "./chroma_db",
        collection_name: str = "documents",
    ):
        self.client = chromadb.PersistentClient(
            path=persist_directory
        )

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(
        self,
        chunks: list[str],
        embeddings: list[list[float]],
        ids: list[str],
        metadatas: list[dict] | None = None,
    ) -> None:
        if not chunks:
            return

        if not (
            len(chunks) == len(embeddings) == len(ids)
        ):
            raise ValueError(
                "Chunks, embeddings, and IDs must have equal lengths"
            )

        self.collection.upsert(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 3,
    ) -> list[dict]:
        if not query_embedding:
            raise ValueError(
                "Query embedding cannot be empty"
            )

        if top_k <= 0:
            raise ValueError(
                "top_k must be greater than zero"
            )

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )

        documents = results["documents"][0]
        ids = results["ids"][0]
        distances = results["distances"][0]
        metadatas = results["metadatas"][0]

        return [
            {
                "id": ids[i],
                "text": documents[i],
                "distance": distances[i],
                "metadata": metadatas[i],
            }
            for i in range(len(documents))
        ]