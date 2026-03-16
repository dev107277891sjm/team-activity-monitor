import hashlib
import io

import mss
from PIL import Image


def capture_all_screens(quality: int = 60, max_width: int = 1920) -> list[tuple[int, bytes, str]]:
    results = []
    with mss.mss() as sct:
        for i, monitor in enumerate(sct.monitors[1:], start=1):
            raw = sct.grab(monitor)
            img = Image.frombytes("RGB", (raw.width, raw.height), raw.rgb)

            if img.width > max_width:
                ratio = max_width / img.width
                new_h = int(img.height * ratio)
                img = img.resize((max_width, new_h), Image.LANCZOS)

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            image_bytes = buf.getvalue()

            gray = img.convert("L").resize((320, 180), Image.NEAREST)
            img_hash = hashlib.md5(gray.tobytes()).hexdigest()

            results.append((i, image_bytes, img_hash))
    return results


def compute_screen_hash() -> str:
    combined = hashlib.md5()
    with mss.mss() as sct:
        for monitor in sct.monitors[1:]:
            raw = sct.grab(monitor)
            img = Image.frombytes("RGB", (raw.width, raw.height), raw.rgb)
            gray = img.convert("L").resize((160, 90), Image.NEAREST)
            combined.update(gray.tobytes())
    return combined.hexdigest()
