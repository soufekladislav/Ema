"""Create PWA icons from the user's ORIGINAL Ema illustration — no generative redraw.

Image source: https://www.freshcrackers.cz/wp-content/uploads/2026/11/pwa-uvod.jpg
The portrait is only cropped and resized. The downloaded original is committed
along with the derived images so runtime never depends on the WordPress site.
"""
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen

from PIL import Image, ImageOps

URL = "https://www.freshcrackers.cz/wp-content/uploads/2026/11/pwa-uvod.jpg"
OUT = Path(__file__).resolve().parents[1] / "static" / "icons"


def main():
    req = Request(URL, headers={"User-Agent": "EMA-PWA-Asset-Build/1.0"})
    with urlopen(req, timeout=30) as response:
        source_bytes = response.read(5_000_001)
    if len(source_bytes) < 1000 or len(source_bytes) > 5_000_000:
        raise RuntimeError("Unexpected original image size; refusing to overwrite icons")
    original = Image.open(BytesIO(source_bytes))
    original.verify()
    original = Image.open(BytesIO(source_bytes)).convert("RGB")
    width, height = original.size
    if width < 350 or height < 350:
        raise RuntimeError("The original portrait is too small for PWA icons")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ema-source.jpg").write_bytes(source_bytes)

    # A simple crop of the ORIGINAL drawing, no retouching or reillustration.
    # Keep Ema's bun and face dominant at home-screen icon size.
    left, top, right, bottom = (
        round(width * .195), round(height * .075),
        round(width * .807), round(height * .701)
    )
    portrait = original.crop((left, top, right, bottom))
    portrait = ImageOps.fit(portrait, (512, 512), method=Image.Resampling.LANCZOS)
    for size, name in (
        (192, "ema-192.png"),
        (512, "ema-512.png"),
        (256, "ema-avatar.png"),
    ):
        resized = portrait.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(OUT / name, "PNG", optimize=True)
        print(f"updated {name}: {size}x{size} from original drawing")

if __name__ == "__main__":
    main()
