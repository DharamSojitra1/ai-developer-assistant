from app.services.llm_service import generate_ai_response

response = generate_ai_response(
    "Explain Gen AI"
)

print(response)