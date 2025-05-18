# Valen Dev Helpers

Microservicio personal para convertir imágenes a WebP y videos a WebM.

## Endpoints

- `POST /convert-image`: convierte imágenes JPG/PNG a WebP.
- `POST /convert-video`: convierte videos MP4 a WebM.

## Seguridad

Este servicio usa autenticación por header:

```
x-api-key: tu_clave
```

## Deploy

Compatible con Render. Usá `render.yaml` para configuración automática.

## Requisitos

- `ffmpeg` debe estar instalado en el entorno.