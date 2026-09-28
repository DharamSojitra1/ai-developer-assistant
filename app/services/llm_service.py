from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import (
    GEMINI_API_KEY,
    MODEL_NAME,
    REQUEST_TIMEOUT,
)

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from google.api_core.exceptions import (
    DeadlineExceeded,
    ServiceUnavailable,
    InternalServerError,
)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type(
        (
            TimeoutError,
            ConnectionError,
            DeadlineExceeded,
            ServiceUnavailable,
            InternalServerError,
        )
    ),
    reraise=True,
)
async def generate_ai_response(
    message: str,
    temperature: float,
    max_tokens: int,
) -> str:

    llm = ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        api_key=GEMINI_API_KEY,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=REQUEST_TIMEOUT,
    )

    response = await llm.ainvoke(message)

    return response.text