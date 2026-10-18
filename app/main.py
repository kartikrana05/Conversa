from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.routers import replies

INDEX_HTML = Path(__file__).parent / "static" / "index.html"

reply_router = replies.router
app = FastAPI(title="Conversa", redirect_slashes=False)

app.include_router(reply_router)


@app.get("/", include_in_schema=False)
async def frontend():
    return FileResponse(INDEX_HTML)


@app.get("/health", tags=["Health"])
async def root():
    return {"message": "Conversa is healthy!"}
