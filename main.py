from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from utils.convert_image import convert_image_to_webp
from utils.convert_video import convert_video_to_webm
import io
import os
import zipfile
from typing import List
from fastapi import status
from fastapi.responses import Response

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
async def convert_image(
    request: Request,
    files: List[UploadFile] = File(...)
):
    check_auth(request)
    
    # Configuración de límites
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB por archivo
    MAX_TOTAL_SIZE = 50 * 1024 * 1024  # 50MB en total
    
    # Verificar número de archivos
    if len(files) > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pueden procesar más de 20 archivos a la vez"
        )
    
    # Verificar tamaño total
    total_size = 0
    for file in files:
        content = await file.read()
        total_size += len(content)
        file.file.seek(0)  # Reset file pointer
        
        # Verificar tamaño individual
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"El archivo {file.filename} excede el tamaño máximo de 10MB"
            )
    
    if total_size > MAX_TOTAL_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"El tamaño total de los archivos ({total_size/1024/1024:.1f}MB) excede el límite de {MAX_TOTAL_SIZE/1024/1024}MB"
        )
    
    # Si es solo un archivo, devolverlo directamente
    if len(files) == 1:
        file = files[0]
        output = await convert_image_to_webp(file)
        return StreamingResponse(
            io.BytesIO(output),
            media_type="image/webp",
            headers={"Content-Disposition": f"attachment; filename={os.path.splitext(file.filename)[0]}.webp"}
        )
    
    # Para múltiples archivos, crear un zip
    zip_io = io.BytesIO()
    with zipfile.ZipFile(zip_io, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file in files:
            try:
                output = await convert_image_to_webp(file)
                filename = os.path.splitext(file.filename)[0] + ".webp"
                zip_file.writestr(filename, output)
            except Exception as e:
                # Si falla un archivo, continuar con los demás
                print(f"Error procesando {file.filename}: {str(e)}")
                continue
    
    zip_io.seek(0)
    
    return Response(
        content=zip_io.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=converted_images.zip"}
    )

@app.post("/convert-video")
async def convert_video(request: Request, file: UploadFile = File(...)):
    check_auth(request)
    output = await convert_video_to_webm(file)
    return StreamingResponse(io.BytesIO(output), media_type="video/webm")
