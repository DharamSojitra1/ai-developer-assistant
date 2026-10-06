from langchain_google_genai import GoogleGenerativeAIEmbeddings

class EmbeddingService:
    def __init__(self):
        self.model = GoogleGenerativeAIEmbeddings(
            model="gemini-embedding-001"
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