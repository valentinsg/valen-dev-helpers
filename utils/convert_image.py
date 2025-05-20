from PIL import Image, ImageOps, ExifTags
import io
import os
from typing import Optional, Union, BinaryIO
import logging

# Configurar logging
logger = logging.getLogger(__name__)

class ImageConversionError(Exception):
    """Excepción personalizada para errores de conversión de imagen"""
    pass

async def convert_image_to_webp(
    file: Union[BinaryIO, object], 
    quality: int = 80,
    method: int = 6,
    preserve_metadata: bool = True,
    auto_orient: bool = True,
    max_dimension: Optional[int] = None
) -> bytes:
    """
    Convierte una imagen a formato WebP con configuraciones avanzadas.
    
    Mejoras implementadas:
    - Validaciones robustas de entrada
    - Manejo mejorado de errores
    - Preservación de metadatos EXIF
    - Corrección automática de orientación
    - Redimensionado opcional
    - Optimización de memoria
    - Logging detallado
    - Soporte para múltiples formatos de entrada
    
    Args:
        file: Archivo de imagen a convertir (UploadFile de FastAPI o similar)
        quality: Calidad de compresión WebP (60-100)
        method: Método de compresión WebP (0-6, mayor número = mejor compresión)
        preserve_metadata: Si preservar metadatos EXIF
        auto_orient: Si corregir automáticamente la orientación según EXIF
        max_dimension: Dimensión máxima para redimensionar (opcional)
    
    Returns:
        bytes: Imagen convertida en formato WebP
        
    Raises:
        ImageConversionError: Si hay errores durante la conversión
        ValueError: Si los parámetros son inválidos
    """
    
    # === VALIDACIONES DE ENTRADA ===
    if not file:
        raise ValueError("No se proporcionó ningún archivo")
    
    if not 60 <= quality <= 100:
        raise ValueError(f"La calidad debe estar entre 60 y 100, recibido: {quality}")
    
    if not 0 <= method <= 6:
        raise ValueError(f"El método debe estar entre 0 y 6, recibido: {method}")
    
    if max_dimension is not None and max_dimension <= 0:
        raise ValueError(f"La dimensión máxima debe ser positiva, recibido: {max_dimension}")
    
    original_filename = getattr(file, 'filename', 'unknown')
    file_size_mb = 0
    
    try:
        # === LEER CONTENIDO DEL ARCHIVO ===
        logger.info(f"Iniciando conversión de {original_filename}")
        
        # Leer el contenido del archivo una sola vez
        if hasattr(file, 'read'):
            input_bytes = await file.read()
        else:
            raise ValueError("El objeto file no tiene método read()")
        
        # === VALIDACIONES DE CONTENIDO ===
        if not input_bytes:
            raise ImageConversionError(f"El archivo '{original_filename}' está vacío")
        
        file_size_mb = len(input_bytes) / (1024 * 1024)
        
        # Validar tamaño máximo (10MB como en la API)
        MAX_SIZE_MB = 10
        if file_size_mb > MAX_SIZE_MB:
            raise ImageConversionError(
                f"El archivo '{original_filename}' ({file_size_mb:.1f}MB) "
                f"excede el tamaño máximo de {MAX_SIZE_MB}MB"
            )
        
        logger.debug(f"Archivo leído: {file_size_mb:.2f}MB")
        
        # === PROCESAR IMAGEN ===
        input_stream = io.BytesIO(input_bytes)
        
        try:
            # Abrir la imagen con PIL
            with Image.open(input_stream) as image:
                logger.debug(f"Imagen original: {image.size}, modo: {image.mode}, formato: {image.format}")
                
                # === VALIDAR FORMATO DE ENTRADA ===
                if image.format not in ['JPEG', 'PNG', 'GIF', 'WEBP', 'BMP', 'TIFF']:
                    raise ImageConversionError(
                        f"Formato de imagen no soportado: {image.format}. "
                        f"Formatos válidos: JPEG, PNG, GIF, WebP, BMP, TIFF"
                    )
                
                # === CORREGIR ORIENTACIÓN SEGÚN EXIF ===
                if auto_orient and hasattr(image, '_getexif'):
                    try:
                        image = ImageOps.exif_transpose(image)
                        logger.debug("Orientación corregida según EXIF")
                    except Exception as e:
                        logger.warning(f"No se pudo corregir orientación EXIF: {e}")
                
                # === PRESERVAR METADATOS EXIF ===
                exif_data = b''
                if preserve_metadata and hasattr(image, 'info') and 'exif' in image.info:
                    try:
                        exif_data = image.info['exif']
                        logger.debug("Metadatos EXIF preservados")
                    except Exception as e:
                        logger.warning(f"No se pudieron preservar metadatos EXIF: {e}")
                
                # === REDIMENSIONAR SI ES NECESARIO ===
                if max_dimension and (image.width > max_dimension or image.height > max_dimension):
                    original_size = image.size
                    image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
                    logger.debug(f"Imagen redimensionada de {original_size} a {image.size}")
                
                # === CONVERTIR MODO DE COLOR ===
                original_mode = image.mode
                
                if image.mode in ("RGBA", "LA"):
                    # Para imágenes con transparencia, convertir a RGB con fondo blanco
                    background = Image.new('RGB', image.size, (255, 255, 255))
                    if image.mode == "RGBA":
                        background.paste(image, mask=image.split()[-1])  # Usar canal alpha como máscara
                    else:  # LA mode
                        background.paste(image, mask=image.split()[-1])
                    image = background
                    logger.debug(f"Convertido de {original_mode} a RGB (fondo blanco)")
                
                elif image.mode == "P":
                    # Para imágenes con paleta, convertir a RGB
                    if 'transparency' in image.info:
                        # Si tiene transparencia, convertir con fondo blanco
                        image = image.convert('RGBA')
                        background = Image.new('RGB', image.size, (255, 255, 255))
                        background.paste(image, mask=image.split()[-1])
                        image = background
                        logger.debug(f"Convertido de {original_mode} a RGB (con transparencia)")
                    else:
                        image = image.convert('RGB')
                        logger.debug(f"Convertido de {original_mode} a RGB")
                
                elif image.mode not in ("RGB", "L"):
                    # Para otros modos, convertir a RGB
                    image = image.convert('RGB')
                    logger.debug(f"Convertido de {original_mode} a RGB")
                
                # === CREAR BUFFER DE SALIDA ===
                output_buffer = io.BytesIO()
                
                # === CONFIGURAR PARÁMETROS DE COMPRESIÓN WEBP ===
                save_kwargs = {
                    'format': 'WEBP',
                    'quality': quality,
                    'method': method,
                    'optimize': True,
                    'lossless': False
                }
                
                # Agregar EXIF si está disponible
                if exif_data and preserve_metadata:
                    save_kwargs['exif'] = exif_data
                
                # === GUARDAR EN FORMATO WEBP ===
                image.save(output_buffer, **save_kwargs)
                
                # === OBTENER RESULTADO ===
                output_bytes = output_buffer.getvalue()
                output_buffer.close()
                
                # === ESTADÍSTICAS DE CONVERSIÓN ===
                output_size_mb = len(output_bytes) / (1024 * 1024)
                compression_ratio = (1 - output_size_mb / file_size_mb) * 100 if file_size_mb > 0 else 0
                
                logger.info(
                    f"✅ Conversión exitosa: {original_filename} "
                    f"({file_size_mb:.2f}MB → {output_size_mb:.2f}MB, "
                    f"{compression_ratio:.1f}% reducción)"
                )
                
                return output_bytes
                
        except Image.UnidentifiedImageError:
            raise ImageConversionError(
                f"No se pudo identificar '{original_filename}' como una imagen válida. "
                f"Verifica que el archivo no esté corrupto y sea un formato de imagen soportado."
            )
        
        except Image.DecompressionBombError:
            raise ImageConversionError(
                f"El archivo '{original_filename}' es demasiado grande para ser procesado de forma segura. "
                f"Reduce las dimensiones de la imagen."
            )
    
    except ImageConversionError:
        # Re-lanzar errores de conversión ya manejados
        raise
    
    except MemoryError:
        raise ImageConversionError(
            f"No hay suficiente memoria para procesar '{original_filename}' ({file_size_mb:.1f}MB). "
            f"Intenta con una imagen más pequeña."
        )
    
    except Exception as e:
        logger.error(f"Error inesperado procesando {original_filename}: {str(e)}", exc_info=True)
        raise ImageConversionError(
            f"Error inesperado al procesar '{original_filename}': {str(e)}"
        )
    
    finally:
        # === LIMPIEZA DE MEMORIA ===
        if 'input_stream' in locals():
            input_stream.close()
        
        # Reset file pointer si es posible
        if hasattr(file, 'seek'):
            try:
                await file.seek(0)
            except Exception:
                pass  # Ignorar errores al hacer seek


def get_image_info(image_bytes: bytes) -> dict:
    """
    Obtiene información detallada de una imagen.
    
    Args:
        image_bytes: Bytes de la imagen
        
    Returns:
        dict: Información de la imagen (formato, dimensiones, modo, etc.)
    """
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            info = {
                'format': image.format,
                'mode': image.mode,
                'size': image.size,
                'width': image.width,
                'height': image.height,
                'has_transparency': 'transparency' in image.info or 'A' in image.mode,
                'size_bytes': len(image_bytes),
                'size_mb': len(image_bytes) / (1024 * 1024)
            }
            
            # Información EXIF si está disponible
            if hasattr(image, '_getexif') and image._getexif():
                exif = image._getexif()
                info['has_exif'] = True
                info['exif_orientation'] = exif.get(274, 1)  # Orientation tag
            else:
                info['has_exif'] = False
                
            return info
            
    except Exception as e:
        return {'error': str(e)}


def estimate_webp_size(width: int, height: int, quality: int = 80) -> float:
    """
    Estima el tamaño aproximado en MB de una imagen WebP.
    
    Args:
        width: Ancho en píxeles
        height: Alto en píxeles  
        quality: Calidad de compresión (60-100)
        
    Returns:
        float: Tamaño estimado en MB
    """
    # Fórmula aproximada basada en datos empíricos
    pixels = width * height
    base_compression = 0.1 + (quality / 100) * 0.4
    estimated_bytes = pixels * base_compression
    return estimated_bytes / (1024 * 1024)


# === FUNCIONES DE UTILIDAD ADICIONALES ===

def validate_image_file(file, max_size_mb: int = 10) -> tuple[bool, str]:
    """
    Valida si un archivo es una imagen válida.
    
    Args:
        file: Archivo a validar
        max_size_mb: Tamaño máximo en MB
        
    Returns:
        tuple: (es_válido, mensaje_error)
    """
    try:
        if not file:
            return False, "No se proporcionó archivo"
        
        if not hasattr(file, 'filename') or not file.filename:
            return False, "Archivo sin nombre"
        
        if not hasattr(file, 'content_type'):
            return False, "Tipo de contenido no disponible"
        
        valid_types = {
            'image/jpeg', 'image/jpg', 'image/png', 
            'image/gif', 'image/webp', 'image/bmp'
        }
        
        if file.content_type not in valid_types:
            return False, f"Tipo no válido: {file.content_type}"
        
        # Validar extensión
        valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if file_ext not in valid_extensions:
            return False, f"Extensión no válida: {file_ext}"
        
        return True, "Válido"
        
    except Exception as e:
        return False, f"Error de validación: {str(e)}"