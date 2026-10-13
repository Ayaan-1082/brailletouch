"""
Real Gemini check — sends one photo to Gemini with the key in config.py,
no camera or backend server needed.

Run from inside the backend/ folder:
    python test_gemini.py path/to/photo.jpg

Try it with:
  - a photo of printed text   -> kind "text", the text, and a short summary
  - a photo with no text      -> kind "scene" and a one-sentence description
Prints how long Gemini took, or the reason it failed.
"""

import asyncio
import sys
import time

from services.gemini_service import read_image, image_type

if len(sys.argv) != 2:
    print("Usage: python test_gemini.py <path_to_photo>")
    sys.exit(1)

with open(sys.argv[1], "rb") as f:
    image_bytes = f.read()

print(f"Sending {sys.argv[1]} ({len(image_bytes) // 1024} KB, {image_type(image_bytes)}) to Gemini...\n")
start = time.perf_counter()
reading = asyncio.run(read_image(image_bytes))
seconds = time.perf_counter() - start

if reading.error:
    print(f"FAILED after {seconds:.1f}s: {reading.error}")
    sys.exit(1)
print(f"Kind:    {reading.kind}")
print(f"Text:    {reading.text or '(none)'}")
print(f"Summary: {reading.summary}  ({len(reading.summary.split())} words, played in Braille)")
print(f"Time:    {seconds:.1f}s")
