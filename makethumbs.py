from pathlib import Path
from PIL import Image, ImageOps
import sys

THUMB_SIZE = (360, 240)
QUALITY = 82

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

# Webbplatsens thumbs-katalog
SITE_THUMBS = Path("C:/Users/mats_/bussprojekt/thumbs")


def build_thumbnail(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)

    if dst.exists():
        return

    try:
        with Image.open(src) as im:

            im = ImageOps.exif_transpose(im)

            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")

            thumb = im.copy()
            thumb.thumbnail(THUMB_SIZE)

            thumb.save(dst, "JPEG", quality=QUALITY, optimize=True)

            print("thumb:", dst)

    except Exception as e:
        print("fail:", src, e)


def main():

    source = Path.cwd()

    print("Källmapp:", source)

    for file in source.rglob("*"):

        if not file.is_file():
            continue

        if file.suffix.lower() not in IMAGE_EXTS:
            continue

        rel = file.relative_to(source)

        dst = SITE_THUMBS / source.name / rel
        dst = dst.with_suffix(".jpg")

        build_thumbnail(file, dst)


if __name__ == "__main__":
    main()