# serve_frontend.py
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import pathlib

app = FastAPI()
script_dir = pathlib.Path(__file__).resolve().parent
static_files_dir = script_dir / "static"

@app.get("/chat")
async def serve_chat_html():
    chat_html_path = static_files_dir / "chat.html"
    if chat_html_path.is_file():
        return FileResponse(chat_html_path)
    raise HTTPException(status_code=404, detail="chat.html not found")

app.mount("/", StaticFiles(directory=static_files_dir, html=True), name="static-frontend")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001) 