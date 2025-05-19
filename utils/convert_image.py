from PIL import Image
import io

async def convert_image_to_webp(file):
    """
    Convierte una imagen a formato WebP
    
    Args:
        file: Archivo de imagen a convertir
        
    Returns:
        bytes: Imagen convertida en formato WebP
    """
    try:
        # Leer el contenido del archivo
        input_bytes = await file.read()
        
        # Verificar si el archivo está vacío
        if not input_bytes:
            raise ValueError("El archivo está vacío")
            
        # Abrir la imagen
        image = Image.open(io.BytesIO(input_bytes))
        
        # Convertir a RGB si es necesario (para formatos con transparencia o paleta)
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        
        # Crear buffer de salida
        output = io.BytesIO()
        
        # Guardar en formato WebP con configuración óptima
        image.save(
            output,
            format="WEBP",
            quality=80,           # Calidad 80% (buena relación calidad/tamaño)
            method=6,             # Método de compresión máximo (0-6)
            lossless=False,       # Compresión con pérdida para mejor relación de compresión
            optimize=True,        # Optimización de tamaño
            exif=image.info.get('exif', b'')  # Preservar metadatos EXIT si existen
        )
        
        # Obtener los bytes de salida
        output_bytes = output.getvalue()
        output.close()
        
        return output_bytes
        
    except Exception as e:
        raise ValueError(f"Error al procesar la imagen {file.filename}: {str(e)}")
    finally:
        # Asegurarse de que el archivo se cierre correctamente
        if 'file' in locals() and hasattr(file, 'file') and not file.file.closed:
            file.file.close()
