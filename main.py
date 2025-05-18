from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from utils.convert_image import convert_image_to_webp
from utils.convert_video import convert_video_to_webm
import io
import os

# Crear app
app = FastAPI()

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4321",
        "https://astro-helpers.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Clave API
API_KEY = os.getenv("API_KEY", "changeme")

def check_auth(request: Request):
    if request.headers.get("x-api-key") != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.post("/convert-image")
async def convert_image(request: Request, file: UploadFile = File(...)):
    check_auth(request)
    output = await convert_image_to_webp(file)
    return StreamingResponse(io.BytesIO(output), media_type="image/webp")

@app.post("/convert-video")
async def convert_video(request: Request, file: UploadFile = File(...)):
    check_auth(request)
    output = await convert_video_to_webm(file)
    return StreamingResponse(io.BytesIO(output), media_type="video/webm")
