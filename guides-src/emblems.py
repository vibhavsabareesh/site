#!/usr/bin/env python3
"""Pull committee emblems out of the poster PDF at full resolution.

Each poster page carries its emblem as its own image XObject (with a soft
mask), so it comes out crisp and already transparent -- far better than
masking the flattened poster JPEG by luminance.

Usage:  python emblems.py "/path/to/Commitee posts.pdf" [outdir]
"""
import os, sys
import pymupdf

# page order in the poster deck -> committee slug
PAGES = {1: "uncsw", 2: "disec", 3: "fia", 4: "ip", 5: "unhrc", 6: "wto",
         7: "icj", 8: "lok-sabha", 9: "unodc", 10: "us-senate", 11: "ccc", 12: "unsc"}


def emblem_xref(page):
    """The emblem is the image that is neither the full-bleed backdrop nor
    one of the two header logos."""
    best = None
    for info in page.get_image_info(xrefs=True):
        x0, y0, x1, y1 = info["bbox"]
        w, h = x1 - x0, y1 - y0
        if w > page.rect.width * 0.9 and h > page.rect.height * 0.9:
            continue                      # backdrop
        if y1 < page.rect.height * 0.2:
            continue                      # header lockup
        if best is None or w * h > best[1]:
            best = (info["xref"], w * h)
    return best[0] if best else None


def trim(path):
    """Drop fully transparent margins so every emblem fills the cover box."""
    try:
        from PIL import Image
    except ImportError:
        return
    im = Image.open(path).convert("RGBA")
    box = im.split()[3].point(lambda a: 255 if a > 8 else 0).getbbox()
    if box and box != (0, 0, im.width, im.height):
        im.crop(box).save(path)


def extract(pdf, outdir):
    doc = pymupdf.open(pdf)
    os.makedirs(outdir, exist_ok=True)
    done = []
    for pno, slug in PAGES.items():
        if pno > doc.page_count:
            continue
        page = doc[pno - 1]
        xref = emblem_xref(page)
        if not xref:
            print(f"  {slug}: no emblem image found")
            continue
        info = doc.extract_image(xref)
        pix = pymupdf.Pixmap(info["image"])
        if info.get("smask"):
            pix = pymupdf.Pixmap(pix, pymupdf.Pixmap(doc.extract_image(info["smask"])["image"]))
        out = os.path.join(outdir, f"{slug}.png")
        pix.save(out)
        trim(out)
        done.append((slug, pix.width, pix.height, bool(info.get("smask"))))
        print(f"  {slug}: {pix.width}x{pix.height} alpha={bool(info.get('smask'))} -> {out}")
    return done


if __name__ == "__main__":
    extract(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "emblems")
