"""Browser checks at the viewport widths required by prompt.md."""
from pathlib import Path
import functools
import http.server
import json
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.tools'))
from playwright.sync_api import sync_playwright
from PIL import Image
import zxingcpp

class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass

server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT)))
threading.Thread(target=server.serve_forever, daemon=True).start()
url = f'http://127.0.0.1:{server.server_port}/'
artifacts = ROOT / 'artifacts'
artifacts.mkdir(exist_ok=True)
results = []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe', headless=True)
    for width in [360, 390, 430, 768, 1024, 1440]:
        context = browser.new_context(viewport={'width': width, 'height': 844 if width < 600 else 1000}, device_scale_factor=2 if width < 600 else 1, is_mobile=width < 600, has_touch=width < 600)
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.add_init_script("window.layoutShift = 0; new PerformanceObserver(list => { for (const e of list.getEntries()) if (!e.hadRecentInput) window.layoutShift += e.value; }).observe({type:'layout-shift', buffered:true});")
        page.goto(url, wait_until='networkidle')
        for section in ['#about', '#technology', '#team', '.footer']:
            page.locator(section).scroll_into_view_if_needed()
            page.wait_for_timeout(250)
        page.evaluate("document.querySelectorAll('img').forEach(i => i.loading='eager')")
        page.wait_for_function("Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)")
        page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
        page.wait_for_timeout(700)
        metrics = page.evaluate("""() => ({
          width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
          overflow: [...document.querySelectorAll('body *')].filter(e => {const r=e.getBoundingClientRect(); return r.width && (r.right>innerWidth+1 || r.left < -1) && !e.classList.contains('skip-link')}).map(e=>e.tagName+'.'+e.className),
          images: [...document.images].every(i=>i.complete && i.naturalWidth>0),
          bodyFont: parseFloat(getComputedStyle(document.body).fontSize),
          smallTargets: [...document.querySelectorAll('a')].filter(e=>!e.classList.contains('skip-link') && (e.getBoundingClientRect().height<44 || e.getBoundingClientRect().width<44)).map(e=>e.textContent),
          cls: window.layoutShift,
          heroSource: document.querySelector('.hero img').currentSrc,
          teamColumns: getComputedStyle(document.querySelector('.team-grid')).gridTemplateColumns
        })""")
        assert metrics['scrollWidth'] == width, metrics
        assert not metrics['overflow'], metrics
        assert metrics['images'] and metrics['bodyFont'] >= 16, metrics
        assert not metrics['smallTargets'], metrics
        assert metrics['cls'] < .01, metrics
        assert not errors, errors
        page.screenshot(path=str(artifacts / f'page-{width}.png'), full_page=True)
        if width == 390:
            page.screenshot(path=str(artifacts / 'mobile-hero.png'))
            page.locator('.qr img').screenshot(path=str(artifacts / 'qr-rendered.png'))
            assert zxingcpp.read_barcode(Image.open(artifacts / 'qr-rendered.png')).text == page.locator('.course-link').get_attribute('href')
            page.locator('.header nav a[href="#about"]').tap()
            page.wait_for_timeout(800)
            assert page.evaluate('location.hash') == '#about'
            with page.expect_popup() as popup:
                page.locator('.scheme-link').tap()
            popup.value.wait_for_load_state()
            assert popup.value.url.endswith('/images/Scheme.png')
            popup.value.close()
        results.append(metrics)
        context.close()
    context = browser.new_context(viewport={'width':390,'height':844}, java_script_enabled=False, reduced_motion='reduce')
    page = context.new_page()
    page.goto(url)
    assert page.locator('#team-title').is_visible()
    assert page.locator('.course-link').get_attribute('href').startswith('https://')
    assert page.locator('.reveal').first.evaluate('(e) => getComputedStyle(e).opacity') == '1'
    context.close()
    context = browser.new_context(viewport={'width':390,'height':844}, reduced_motion='reduce')
    page = context.new_page()
    page.goto(url)
    assert page.evaluate('getComputedStyle(document.documentElement).scrollBehavior') == 'auto'
    assert page.locator('.is-visible').count() == 0
    context.close()
    browser.close()
server.shutdown()
(artifacts / 'checks.json').write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(results, indent=2, ensure_ascii=False))
print('PASS: six widths, image loading, touch targets, QR decoding, navigation, scheme popup, no JavaScript, reduced motion.')
