from PIL import Image
import io

async def convert_image_to_webp(file):
    input_bytes = await file.read()
    image = Image.open(io.BytesIO(input_bytes))

    # Convert to RGB if image has alpha or is in palette mode
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")

    output = io.BytesIO()
    image.save(
        output,
        format="WEBP",
        quality=80,          # Bajamos a 70 para más compresión
        method=6,            # Método de compresión máximo (0–6)
        lossless=False,      # Lossy = mejor compresión
        optimize=True        # Elimina metadatos innecesarios
    )
    output.seek(0)
    return output.getvalue()
