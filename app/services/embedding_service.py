from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.config import EMBEDDING_MODEL_NAME


class EmbeddingService:
    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME):
        self.model_name = model_name
        self.model = GoogleGenerativeAIEmbeddings(
            model=model_name
        )
    
    async def embed_documents(
        self,
        texts: list[str]
    ) -> list[list[float]]:
        if not texts:
            return []
        return await self.model.aembed_documents(texts)
    
    async def embed_query(
        self,
        text: str
    ) -> list[float]:
        if not text.strip():
            raise ValueError("Query cannot be empty")
        return await self.model.aembed_query(text)
