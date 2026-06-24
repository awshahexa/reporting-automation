import sys, fitz, pytesseract, io, re
from pathlib import Path
from PIL import Image

path = r"failed\PO_DFREE_ACC_20260611.pdf"
doc = fitz.open(path)
print(f"Pages: {len(doc)}")

native = ""
for p in doc:
    native += p.get_text("text")
print(f"Native text length: {len(native.strip())}")

for i in range(len(doc)):
    pix = doc[i].get_pixmap(dpi=200)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    t = pytesseract.image_to_string(img)
    print(f"=== PAGE {i+1} ===")
    print(t[:800])
    print()
doc.close()
