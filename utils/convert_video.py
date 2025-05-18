import subprocess
import tempfile
import os

async def convert_video_to_webm(file):
    input_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    output_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".webm")

    input_data = await file.read()
    with open(input_temp.name, "wb") as f:
        f.write(input_data)

    command = [
        "ffmpeg", "-i", input_temp.name,
        "-c:v", "libvpx-vp9", "-b:v", "1M",
        "-c:a", "libopus",
        output_temp.name
    ]

    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    with open(output_temp.name, "rb") as f:
        result = f.read()

    os.unlink(input_temp.name)
    os.unlink(output_temp.name)

    return result