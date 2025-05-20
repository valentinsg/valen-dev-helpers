import uvicorn
import os

if __name__ == "__main__":
    # Cargar variables de entorno desde .env si existe
    if os.path.exists('.env'):
        from dotenv import load_dotenv
        load_dotenv()
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload en desarrollo
        log_level="info"
    )