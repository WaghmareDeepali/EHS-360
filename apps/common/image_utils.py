from io import BytesIO
from PIL import Image
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.uploadedfile import SimpleUploadedFile
from pathlib import Path
import tempfile
import subprocess
import shutil
import os
import sys

def compress_image(uploaded_file, max_width=1024, max_height=1024, quality=75):
    """
    Compress uploaded image file.
    """
    # Open image with PIL
    image = Image.open(uploaded_file)
    image_format = image.format

    # Convert RGBA to RGB to avoid errors with JPEG
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")

    # Resize maintaining aspect ratio
    image.thumbnail((max_width, max_height), Image.LANCZOS)

    # Save to BytesIO
    output = BytesIO()
    image.save(output, format=image_format, quality=quality, optimize=True)
    output.seek(0)

    # Create new Django InMemoryUploadedFile
    compressed_file = InMemoryUploadedFile(
        output, 
        'ImageField',
        uploaded_file.name,
        uploaded_file.content_type,
        sys.getsizeof(output),
        None
    )
    return compressed_file


def compress_video(uploaded_file, crf=32, max_height=720):
    """
    Compress uploaded video with ffmpeg when available.
    Falls back to the original upload if compression tooling is unavailable.
    """
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        return uploaded_file

    suffix = Path(uploaded_file.name).suffix or ".mp4"
    temp_input_path = None
    temp_output_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_input:
            temp_input_path = temp_input.name
            if hasattr(uploaded_file, "chunks"):
                for chunk in uploaded_file.chunks():
                    temp_input.write(chunk)
            else:
                temp_input.write(uploaded_file.read())

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_output:
            temp_output_path = temp_output.name

        command = [
            ffmpeg_path,
            "-y",
            "-i",
            temp_input_path,
            "-vf",
            f"scale='min(iw,1280)':'min(ih,{max_height})':force_original_aspect_ratio=decrease",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            str(crf),
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-movflags",
            "+faststart",
            temp_output_path,
        ]
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        with open(temp_output_path, "rb") as compressed_file:
            compressed_bytes = compressed_file.read()

        compressed_name = f"{Path(uploaded_file.name).stem}.mp4"
        return SimpleUploadedFile(
            compressed_name,
            compressed_bytes,
            content_type="video/mp4"
        )
    except Exception:
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)
        return uploaded_file
    finally:
        for path in [temp_input_path, temp_output_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
