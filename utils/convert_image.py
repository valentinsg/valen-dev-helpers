from PIL import Image
import io

async def convert_image_to_webp(file):
    image = Image.open(io.BytesIO(await file.read()))
    output = io.BytesIO()
    image.save(output, format="WEBP", quality=85)
    return output.getvalue()