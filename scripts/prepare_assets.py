"""Generate optimized local assets; originals are preserved."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.tools'))
from PIL import Image
import zxingcpp

source = ROOT / 'images'
output = source / 'optimized'
output.mkdir(exist_ok=True)

def webp(original, name, widths, crop=None, lossless=False):
    with Image.open(source / original) as image:
        if crop:
            image = image.crop(crop)
        for width in widths:
            height = round(image.height * width / image.width)
            resized = image.resize((width, height), Image.Resampling.LANCZOS)
            suffix = f'-{width}' if len(widths) > 1 else ''
            resized.save(output / f'{name}{suffix}.webp', quality=82, method=6, lossless=lossless)

webp('main_desktop.png', 'main-desktop', [960, 1600, 2007])
# Square crop retains both outer edges and the crown of the central arch.
webp('main.png', 'main-mobile', [640, 960], crop=(365, 0, 1306, 941))
webp('technology.jpg', 'technology', [640, 1280])
webp('Scheme.png', 'scheme', [1366], lossless=True)
webp('logo1.jpg', 'tgasu', [260])
webp('logo1.png', 'smart-build', [300])
webp('logo3.png', 'kursiv', [560])
with Image.open(source / 'qr.png') as qr:
    url = zxingcpp.read_barcode(qr).text
    qr.resize((300, 300), Image.Resampling.LANCZOS).save(output / 'qr.png', optimize=True)
    assert zxingcpp.read_barcode(Image.open(output / 'qr.png')).text == url
page = ROOT / 'index.html'
page.write_text(page.read_text(encoding='utf-8').replace('COURSE_URL', url), encoding='utf-8')
print('QR destination:', url)
for asset in output.iterdir():
    print(asset.name, asset.stat().st_size)
