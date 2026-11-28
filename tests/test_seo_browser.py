"""Exercise public /rama-db/ links with JS enabled and disabled."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import threading
import unittest
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class ProjectPages(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        if path.startswith("/rama-db/"):
            path = path[len("/rama-db"):]
        return super().translate_path(path)

    def log_message(self, *args):
        pass


class SeoBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(ProjectPages,directory=ROOT))
        cls.addClassCleanup(server.server_close)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        cls.addClassCleanup(server.shutdown)
        cls.base = f"http://127.0.0.1:{server.server_port}/rama-db/"
        pw = sync_playwright().start()
        cls.addClassCleanup(pw.stop)
        cls.chromium = pw.chromium.launch(executable_path=shutil.which("chromium"))
        cls.addClassCleanup(cls.chromium.close)

    def new_page(self, **kwargs):
        context = self.chromium.new_context(**kwargs)
        self.addCleanup(context.close)
        page = context.new_page()
        context.route("https://**",lambda r:r.abort())
        errors = []
        page.on("pageerror",lambda e:errors.append(str(e)))
        self.addCleanup(self.assertEqual,errors,[])
        return page

    def test_sharing_links_and_timecode(self):
        p = self.new_page(viewport={"width":390,"height":844},is_mobile=True,has_touch=True,
                          permissions=["clipboard-read","clipboard-write"])
        p.goto(self.base+"#cat=shelling")
        p.locator("#shareTopic").click()
        dialog = p.locator(".share-dialog")
        expect(dialog.locator("input")).to_have_value(self.base+"topics/shelling/")
        p.keyboard.press("Escape")
        first = p.locator("#results button.stamp").first
        key = first.get_attribute("data-open")
        row = p.evaluate("id => RAMA_DB.items.find(i=>i.id===id)",key)
        first.click()
        p.locator("#detail button[data-share-url]").click()
        url = self.base+f'video/{row["video"]}/?t={row["seconds"]}'
        expect(dialog.locator("input")).to_have_value(url)
        for attr in ("facebook","telegram","whatsapp"):
            params = parse_qs(urlsplit(dialog.locator(f"[data-{attr}]").get_attribute("href")).query)
            self.assertTrue(any(url in v for vals in params.values() for v in vals))
        dialog.locator("[data-copy]").click()
        expect(dialog.get_by_role("status")).to_have_text("Ссылка скопирована")
        self.assertEqual(p.evaluate("navigator.clipboard.readText()"),url)
        self.assertTrue(p.goto(url).ok)
        p.reload()
        expect(p.locator("[data-current-chapter]")).to_have_text(row["title"])
        self.assertTrue(p.locator("iframe").get_attribute("src").endswith("?start="+str(row["seconds"])))
        expect(p.locator('[aria-current="time"]')).to_have_id(row["id"])
        p.locator("[data-current-share]").click()
        expect(dialog.locator("input")).to_have_value(url)
        p.keyboard.press("Escape")
        for width in (320,390,768,820,1366):
            p.set_viewport_size({"width":width,"height":850})
            self.assertLessEqual(p.evaluate("document.documentElement.scrollWidth"),width)

    def test_bot_navigation_without_javascript(self):
        p = self.new_page(java_script_enabled=False)
        p.goto(self.base)
        p.get_by_role("link",name="Тематический указатель").click()
        p.get_by_role("link",name="Война в Украине и общество",exact=True).click()
        p.get_by_role("link",name="Семинар о войне в Украине",exact=True).click()
        expect(p.locator("h1")).to_have_text("Семинар о войне в Украине")
        p.locator("main h2 a").first.click()
        expect(p.locator("iframe.watch-player")).to_have_count(1)
        self.assertTrue(p.reload().ok)
        self.assertIn("/rama-db/video/",p.url)
        self.assertEqual(p.goto(self.base+"missing-route/").status,404)

    def test_mobile_native_share(self):
        p = self.new_page()
        p.add_init_script("navigator.share = async data => {window.shared = data}")
        p.goto(self.base+"topics/gita/")
        p.locator("button[data-share-url]").first.click()
        p.locator("[data-native]").click()
        self.assertEqual(p.evaluate("window.shared.url"),self.base+"topics/gita/")
