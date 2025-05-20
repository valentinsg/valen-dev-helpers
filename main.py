# main.py
from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.responses import StreamingResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from utils.convert_image import convert_image_to_webp
from utils.convert_video import convert_video_to_webm
import io
import os
import zipfile
import time
from typing import List, Optional
from fastapi import status
from collections import defaultdict

# === CREAR APP ===
app = FastAPI(
    title="Image/Video Converter API",
    description="API para convertir imágenes a WebP y videos a WebM",
    version="1.0.0"
)

# === CONFIGURAR CORS ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4321",
        "https://astro-helpers.vercel.app",
        "http://localhost:3000",
        "https://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === CONFIGURACIÓN Y CONSTANTES ===
API_KEY = os.getenv("API_KEY", "changeme")
RATE_LIMIT_REQUESTS = 20
RATE_LIMIT_WINDOW = 60

# === RATE LIMITING ===
request_counts = defaultdict(list)

def check_rate_limit(client_ip: str):
    """Verifica el rate limiting por IP"""
    current_time = time.time()
    requests = request_counts[client_ip]
    
    # Limpiar requests antiguos
    request_counts[client_ip] = [req_time for req_time in requests 
                                if current_time - req_time < RATE_LIMIT_WINDOW]
    
    # Verificar límite
    if len(request_counts[client_ip]) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Demasiadas solicitudes. Límite: {RATE_LIMIT_REQUESTS} por minuto. Inténtalo en {RATE_LIMIT_WINDOW} segundos."
        )
    
    # Agregar nueva request
    request_counts[client_ip].append(current_time)

def check_auth(request: Request):
    """Verifica la autenticación mediante API key"""
    api_key = request.headers.get("x-api-key")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="API Key requerida. Incluye 'x-api-key' en los headers."
        )
    
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="API Key inválida. Verifica tu clave de acceso."
        )

def get_client_ip(request: Request) -> str:
    """Obtiene la IP real del cliente considerando proxies"""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    
    return request.client.host

# === ENDPOINTS ===
@app.post("/convert-image")
async def convert_image(
    request: Request,
    file: Optional[UploadFile] = File(None),
    files: Optional[List[UploadFile]] = File(None),
    quality: Optional[int] = 80
):
    """Convierte una o múltiples imágenes a formato WebP"""
    
    try:
        # Verificaciones de seguridad
        client_ip = get_client_ip(request)
        check_rate_limit(client_ip)
        check_auth(request)
        
        # Configuración de límites
        MAX_FILE_SIZE = 10 * 1024 * 1024
        MAX_TOTAL_SIZE = 50 * 1024 * 1024
        MAX_FILES = 20
        ALLOWED_TYPES = {
            'image/jpeg', 'image/jpg', 'image/png', 
            'image/gif', 'image/webp', 'image/bmp'
        }
        
        # Validar parámetros
        if quality is not None and (quality < 60 or quality > 100):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La calidad debe estar entre 60 y 100"
            )
        
        # Procesar archivos de entrada
        processed_files = []
        
        if file and file.filename:
            processed_files = [file]
        elif files and len(files) > 0 and files[0].filename:
            processed_files = files
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se han proporcionado archivos para convertir."
            )
        
        # Validaciones de archivos
        if len(processed_files) > MAX_FILES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se pueden procesar más de {MAX_FILES} archivos simultáneamente"
            )
        
        total_size = 0
        validated_files = []
        
        for uploaded_file in processed_files:
            content = await uploaded_file.read()
            await uploaded_file.seek(0)
            
            if not content:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El archivo '{uploaded_file.filename}' está vacío"
                )
            
            if uploaded_file.content_type not in ALLOWED_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Tipo de archivo no válido: {uploaded_file.filename}"
                )
            
            file_size = len(content)
            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"El archivo '{uploaded_file.filename}' excede el tamaño máximo"
                )
            
            total_size += file_size
            validated_files.append((uploaded_file, content))
        
        if total_size > MAX_TOTAL_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"El tamaño total excede el límite de {MAX_TOTAL_SIZE/1024/1024}MB"
            )
        
        # Procesar conversiones
        conversion_results = []
        failed_conversions = []
        
        for uploaded_file, content in validated_files:
            try:
                output = await convert_image_to_webp(uploaded_file, quality or 80)
                original_name = uploaded_file.filename
                name_without_ext = os.path.splitext(original_name)[0]
                output_filename = f"{name_without_ext}.webp"
                conversion_results.append((output_filename, output))
                
                print(f"✅ Convertido: {original_name} -> {output_filename}")
                
            except Exception as e:
                error_msg = f"Error al procesar '{uploaded_file.filename}': {str(e)}"
                failed_conversions.append(error_msg)
                print(f"❌ {error_msg}")
                continue
        
        if not conversion_results:
            error_details = "No se pudo procesar ningún archivo."
            if failed_conversions:
                error_details += " Errores: " + "; ".join(failed_conversions)
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_details
            )
        
        # Retornar resultado
        if len(conversion_results) == 1:
            filename, output_data = conversion_results[0]
            
            return StreamingResponse(
                io.BytesIO(output_data),
                media_type="image/webp",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}",
                    "X-Converted-Files": "1",
                    "X-Failed-Files": str(len(failed_conversions))
                }
            )
        
        else:
            # Crear ZIP para múltiples archivos
            zip_io = io.BytesIO()
            
            with zipfile.ZipFile(zip_io, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zip_file:
                for filename, output_data in conversion_results:
                    zip_file.writestr(filename, output_data)
                
                if failed_conversions:
                    error_log = "ARCHIVOS QUE NO PUDIERON SER PROCESADOS:\n\n"
                    error_log += "\n".join(f"❌ {error}" for error in failed_conversions)
                    zip_file.writestr("conversion_errors.txt", error_log)
            
            zip_io.seek(0)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            zip_filename = f"converted_images_{timestamp}.zip"
            
            return Response(
                content=zip_io.getvalue(),
                media_type="application/zip",
                headers={
                    "Content-Disposition": f"attachment; filename={zip_filename}",
                    "X-Converted-Files": str(len(conversion_results)),
                    "X-Failed-Files": str(len(failed_conversions)),
                    "X-Total-Size": str(total_size)
                }
            )
    
    except HTTPException:
        raise
    
    except Exception as e:
        print(f"❌ Error inesperado: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor durante la conversión."
        )

@app.post("/convert-video")
async def convert_video(request: Request, file: UploadFile = File(...)):
    """Convierte videos a formato WebM"""
    client_ip = get_client_ip(request)
    check_rate_limit(client_ip)
    check_auth(request)
    
    try:
        output = await convert_video_to_webm(file)
        return StreamingResponse(
            io.BytesIO(output), 
            media_type="video/webm",
            headers={
                "Content-Disposition": f"attachment; filename={os.path.splitext(file.filename)[0]}.webm"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al procesar el video: {str(e)}"
        )

@app.get("/health")
async def health_check():
    """Endpoint de salud"""
    return {
        "status": "healthy",
        "service": "Image/Video Converter API",
        "timestamp": time.time(),
        "rate_limit": f"{RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW}s"
    }

@app.get("/info")
async def get_info():
    """Información sobre límites y capacidades"""
    return {
        "limits": {
            "max_file_size_mb": 10,
            "max_total_size_mb": 50,
            "max_files_per_request": 20,
            "rate_limit_per_minute": RATE_LIMIT_REQUESTS
        },
        "supported_formats": {
            "input": ["JPEG", "PNG", "GIF", "WebP", "BMP"],
            "output": ["WebP"]
        },
        "features": [
            "Batch conversion",
            "Quality adjustment",
            "Rate limiting",
            "ZIP packaging for multiple files"
        ]
    }

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Manejador global de errores"""
    print(f"❌ Error no manejado: {str(exc)}")
    return Response(
        status_code=500,
        content="Error interno del servidor",
        media_type="text/plain"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)