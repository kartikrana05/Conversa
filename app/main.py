from fastapi import FastAPI

from app.routers import replies


reply_router = replies.router
app = FastAPI(title="Conversa", redirect_slashes=False)

app.include_router(reply_router)

@app.get("/health", tags=["Health"])
async def root():
    return {"message": "Conversa is healthy!"}