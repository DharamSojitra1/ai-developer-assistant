from app.config import MOCK_MODE
from app.services.llm_service import generate_ai_response

async def generate_response(message: str,temperature: float,max_tokens: int) -> str:

    if MOCK_MODE:
        return f"Mock response: {message}"

    return await generate_ai_response(message, temperature, max_tokens)