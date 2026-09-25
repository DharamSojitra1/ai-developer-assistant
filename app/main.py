from fastapi import FastAPI, HTTPException
from app.routes.chat import router as chat_router

app = FastAPI()
app.include_router(chat_router)


@app.get("/")
async def root():
    return {"message": "AI Developer Assistant API"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
