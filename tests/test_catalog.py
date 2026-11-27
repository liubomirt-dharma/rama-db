"""Run with python -m unittest discover -s tests -v (Playwright + Chromium)."""
import hashlib
import json
import os
import re
import shutil
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = re.compile(r"window\.RAMA_DB = (.*?);\s*</script>", re.S)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class Catalog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handler = partial(QuietHandler, directory=ROOT)
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.addClassCleanup(server.server_close)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        cls.addClassCleanup(server.shutdown)
        cls.url = os.environ.get("RAMA_TEST_URL", f"http://127.0.0.1:{server.server_port}/")
        pw = sync_playwright().start()
        cls.addClassCleanup(pw.stop)
        cls.browser = pw.chromium.launch(executable_path=shutil.which("chromium"))
        cls.addClassCleanup(cls.browser.close)

    def setUp(self):
        self.page = self.browser.new_page(viewport={"width": 1280, "height": 800})
        self.addCleanup(self.page.context.close)
        self.errors = []
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        origin = urlsplit(self.url).netloc
        self.page.route("**/*", lambda r: r.continue_() if urlsplit(r.request.url).netloc == origin else r.abort())
        response = self.page.goto(self.url)
        self.assertTrue(response.ok)
        self.db = self.page.evaluate("window.RAMA_DB")
        self.items = self.db["items"]
        self.payload = PAYLOAD.search(response.text())[1]

    def tearDown(self):
        self.assertEqual(self.errors, [])

    def count(self):
        return int(re.sub(r"\D", "", self.page.locator("#count").inner_text()))

    def test_inventory(self):
        self.assertEqual(hashlib.sha256(self.payload.encode()).hexdigest(),
                         "1d938be8dde1b9f4ea8d0ad04c145c31ea3d00ee2c8d6550a5228ae393033814")
        d = self.db
        for key in ("sections", "categories", "videos", "items"):
            self.assertEqual(len(d[key]), len({row["id"] for row in d[key]}))
        videos = {v["id"] for v in d["videos"]}
        cats = {c["id"] for c in d["categories"]}
        self.assertEqual(len(videos), 141)
        self.assertEqual(sum(i["seconds"] is not None for i in self.items), 2099)
        self.assertEqual(sum(len(i["cats"]) for i in self.items), 3678)
        self.assertEqual(sum(len(v["references"]) for v in d["videos"]), 80)
        self.assertEqual(sum(len(v["descriptions"]) for v in d["videos"]), 136)
        for i in self.items:
            self.assertIn(i["video"], videos)
            self.assertTrue(set(i["cats"]) <= cats)
            self.assertEqual(len(i["cats"]), len(set(i["cats"])))
            self.assertTrue(i["seconds"] is None or isinstance(i["seconds"], int) and i["seconds"] >= 0)

    def test_all_topics(self):
        cats = self.db["categories"]
        active = [c for c in cats if c["active"]]
        sections = self.db["sections"]
        self.assertEqual((len(active), len(sections)), (47, 8))
        for video_mode in (False, True):
            if video_mode:
                self.page.locator("#videos").click()
            for row in sections + active:
                category = "section" in row
                keys = {row["id"]} if category else {c["id"] for c in cats if c["section"] == row["id"]}
                items = [i for i in self.items if keys.intersection(i["cats"])]
                expected = len({i["video"] for i in items}) if video_mode else sum(i["type"] != "service" for i in items)
                with self.subTest(row=row["id"], videos=video_mode):
                    self.assertGreater(expected, 0)
                    attr = "data-cat" if category else "data-section-select"
                    button = self.page.locator(f'#categories [{attr}="{row["id"]}"]')
                    details = button.locator("..")
                    if not details.evaluate("d => d.open"):
                        details.locator("summary").click()
                    self.assertEqual(int(button.locator("small").inner_text()), expected)
                    button.click()
                    self.assertEqual(self.count(), expected)
                    self.assertEqual(self.page.locator("#heading").inner_text(), row["name"])
                    self.assertEqual(self.page.locator(".result").count(), min(24, expected))

    def test_video_dialogs(self):
        page = self.page
        page.locator("#videos").click()
        while page.locator("#more").is_visible():
            page.locator("#more").click()
        self.assertEqual(page.locator(".result").count(), 141)
        for v in self.db["videos"]:
            page.locator(f'.primary[data-open="video:{v["id"]}"]').click()
            dialog = page.locator("#detail[open]")
            self.assertEqual(dialog.locator("h2").inner_text(), v["title"])
            self.assertEqual(dialog.locator("iframe").get_attribute("src"),
                             f'https://www.youtube-nocookie.com/embed/{v["id"]}?start=0')
            times = sorted(i["seconds"] for i in self.items if i["video"] == v["id"] and i["seconds"] is not None)
            hrefs = dialog.locator(".chapter a").evaluate_all("links => links.map(a => a.href)")
            self.assertEqual(hrefs, [f'https://www.youtube.com/watch?v={v["id"]}&t={t}s' for t in times])
            self.assertEqual(dialog.locator(".detailslinks a").evaluate_all("links => links.map(a => a.getAttribute('href'))"),
                             page.evaluate("rs => rs.map(r => new URL(r.url).href)", v["references"]))
            for ref in v["references"]:
                self.assertIn(urlsplit(ref["url"]).scheme, ("http", "https"))
            for description in v["descriptions"]:
                self.assertIn(description.strip(), dialog.text_content())
            page.keyboard.press("Escape")
            page.locator("#detail iframe").wait_for(state="detached")

    def test_fragment_player(self):
        page = self.page
        button = page.locator(".primary[data-open]").first
        item = next(i for i in self.items if i["id"] == button.get_attribute("data-open"))
        self.assertGreater(item["seconds"], 0)
        button.click()
        dialog = page.get_by_role("dialog", name=item["title"], exact=True)
        self.assertEqual(dialog.locator("iframe").get_attribute("src"),
                         f'https://www.youtube-nocookie.com/embed/{item["video"]}?start={item["seconds"]}')
        self.assertEqual(dialog.locator("a.primary").get_attribute("href"),
                         f'https://www.youtube.com/watch?v={item["video"]}&t={item["seconds"]}s')
        for link in dialog.locator('a[target="_blank"]').all():
            self.assertIn("noopener", link.get_attribute("rel").split())
        dialog.locator("#close").click()
        dialog.wait_for(state="hidden")

    def test_filters_and_storage(self):
        p = self.page
        p.locator('#quick [data-cat]').click()
        p.go_back()
        self.assertEqual(self.count(), 2005)
        p.go_forward()
        self.assertLess(self.count(), 2005)
        p.locator("#clearFilters").click()
        self.assertEqual(self.count(), 2005)
        p.locator("#kind").select_option("service")
        self.assertEqual(self.count(), 132)
        p.locator("#kind").select_option("all")
        for order in ("old", "new"):
            p.locator("#sort").select_option(order)
            dates = p.locator(".result .meta").all_text_contents()
            dates = [re.search(r"\d{4}-\d{2}-\d{2}$", s)[0] for s in dates]
            self.assertEqual(dates, sorted(dates, reverse=order == "new"))
        p.locator("#quick [data-query='Карма']").click()
        self.assertEqual(self.count(), 111)
        self.assertGreater(p.locator("mark").count(), 0)
        for query in ('"духовная жизнь"', 'карма дхарма', 'нетсовпаденийxyz'):
            p.locator("#search").fill(query)
            p.locator("#search").press("Enter")
            terms = query.strip('"').lower().split() if '"' not in query else [query.strip('"')]
            names = {c["id"]: c["name"] for c in self.db["categories"]}
            expected = 0
            for i in self.items:
                text = " ".join([i["title"], *(names[c] for c in i["cats"]), *i["keywords"]]).lower().replace("ё", "е")
                expected += all(term in text for term in terms)
            self.assertEqual(self.count(), expected)
        p.locator("#reset").click()
        p.locator("#search").fill("Карма")
        p.locator("#search").press("Enter")
        narrow = self.count()
        p.locator("#scope").select_option("context")
        self.assertGreater(self.count(), narrow)
        bookmark = p.locator("[data-bookmark]").first
        key = bookmark.get_attribute("data-bookmark")
        bookmark.click()
        p.locator("#theme").click()
        p.locator("#saved").click()
        p.reload()
        self.assertEqual(self.count(), 1)
        self.assertEqual(p.locator("[data-bookmark]").get_attribute("data-bookmark"), key)
        self.assertTrue(p.locator("body.light").count())
        p.locator("[data-bookmark]").click()
        self.assertEqual(self.count(), 0)
        p.evaluate("location.hash='mode=videos&sort=old'")
        p.wait_for_function("document.querySelector('#videos').classList.contains('active')")
        self.assertEqual(self.count(), 141)

    def test_layout_and_metadata(self):
        p = self.page
        self.assertEqual(p.locator("html").get_attribute("lang"), "ru")
        self.assertIn("Rama DB", p.title())
        self.assertTrue(p.locator("meta[name=description]").get_attribute("content"))
        self.assertEqual(p.locator("link[rel=canonical]").get_attribute("href"), "https://liubomirt-dharma.github.io/rama-db/")
        for width in (320, 375, 768, 1024, 1440):
            p.set_viewport_size({"width": width, "height": 800})
            self.assertLessEqual(p.evaluate("document.documentElement.scrollWidth"), width)
            self.assertTrue(p.locator(".logo").evaluate("""logo => {
                const text = document.createRange();
                text.selectNodeContents(logo);
                const bounds = text.getBoundingClientRect(), box = logo.getBoundingClientRect();
                return bounds.top >= box.top && bounds.bottom <= box.bottom;
            }"""))
            if width <= 850:
                button = p.locator("#mobileCategories")
                button.click()
                p.locator('#categories [data-section-select="war"]').click()
                self.assertEqual(button.get_attribute("aria-expanded"), "false")
