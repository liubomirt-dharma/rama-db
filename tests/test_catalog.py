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

from playwright.sync_api import expect, sync_playwright

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

    def test_people_directory(self):
        p = self.page
        entry = p.locator("aside #categoryPanel").get_by_role("link", name="Личности", exact=True)
        self.assertEqual(p.locator("header").get_by_role("link", name="Личности").count(), 0)
        entry.click()
        p.locator("#peopleDirectory").wait_for()
        p.go_back()
        p.set_viewport_size({"width": 320, "height": 720})
        expect(entry).to_be_hidden()
        p.locator("#mobileCategories").click()
        entry.click()
        p.locator("#peopleDirectory").wait_for()
        self.assertLessEqual(p.evaluate("document.documentElement.scrollWidth"), 320)
        links = p.locator("#peopleList a")
        names = links.locator("span").all_text_contents()
        self.assertEqual(len(set(names)), 68)
        self.assertNotIn("Киев", names)
        self.assertIn("Шрила Прабхупада", names)
        total = 0
        for name in names:
            with self.subTest(name=name):
                expected = {i["id"] for i in self.items if name in i["keywords"]}
                link = links.filter(has=p.get_by_text(name, exact=True))
                self.assertEqual(int(link.locator("small").inner_text()), len(expected))
                link.click()
                expect(p.locator("#heading")).to_have_text(name)
                self.assertEqual(self.count(), len(expected))
                while p.locator("#more").is_visible():
                    p.locator("#more").click()
                ids = p.locator(".primary[data-open]").evaluate_all("buttons => buttons.map(b => b.dataset.open)")
                self.assertCountEqual(ids, expected)
                total += len(ids)
                p.go_back()
                p.locator("#peopleDirectory").wait_for()
        self.assertNotIn("Туласи Валлабха прабху", names)
        self.assertEqual(total, 325)
        links.filter(has_text="Шрила Прабхупада").click()
        expect(p.locator("#heading")).to_have_text("Шрила Прабхупада")
        p.locator("#videos").click()
        expected_videos = {i["video"] for i in self.items if "Шрила Прабхупада" in i["keywords"]}
        self.assertEqual(self.count(), len(expected_videos))
        p.reload()
        self.assertEqual(self.count(), len(expected_videos))
        p.locator(".primary[data-open]").first.click()
        self.assertTrue(p.locator("#detail iframe").is_visible())
        p.locator("#close").click()
        p.locator("#clearFilters").click()
        self.assertEqual(self.count(), 141)

    def test_catalog_views(self):
        p = self.page
        results = p.locator("#results")
        expect(results).to_have_attribute("data-layout", "list")
        p.goto(self.url + "#cat=mobilization&sort=old")
        while p.locator("#more").is_visible():
            p.locator("#more").click()
        def visible_ids():
            return p.locator(".result .primary").evaluate_all("bs => bs.map(b => b.dataset.open)")
        original = visible_ids()
        self.assertEqual(len(original), 44)
        expected = {i["id"]: i for i in self.items if i["id"] in original}
        video_ids = {i["video"] for i in expected.values()}
        p.locator("#groupBy").check()
        for layout in ("grid", "text", "list"):
            p.locator(f"#layouts [data-layout={layout}]").click()
            expect(p.locator("#groupBy")).to_be_checked()
            while p.locator("#more").is_visible():
                p.locator("#more").click()
            self.assertCountEqual(visible_ids(), original)
            self.assertIn(f"{len(video_ids)} видео", p.locator("#count").inner_text())
            self.assertEqual(results.locator("img").count(), 0 if layout == "text" else len(video_ids))
            for group in results.locator(".video-group").all():
                ids = group.locator(".primary").evaluate_all("bs => bs.map(b => b.dataset.open)")
                times = [expected[i]["seconds"] for i in ids if expected[i]["seconds"] is not None]
                self.assertEqual(times, sorted(times))
                self.assertEqual({expected[i]["video"] for i in ids}, {group.get_attribute("data-video")})
        p.locator("#collapseAll").click()
        self.assertEqual(results.locator(".video-group[open]").count(), 0)
        p.locator("#expandAll").click()
        self.assertGreater(results.locator(".video-group[open]").count(), 0)
        p.locator("#groupBy").uncheck()
        self.assertEqual(visible_ids(), original)
        self.assertEqual(p.locator("#sort").input_value(), "old")
        p.locator("#layouts [data-layout=text]").click()
        requests = []
        p.on("request", lambda req: requests.append(req.url))
        p.reload()
        expect(results).to_have_attribute("data-layout", "text")
        self.assertEqual(results.locator("img").count(), 0)
        self.assertFalse(any("i.ytimg.com" in u for u in requests))
        p.locator("#videos").click()
        expect(results).to_have_attribute("data-layout", "grid")
        p.locator(".result a[href^='#source=']").first.click()
        expect(p.locator("#fragments")).to_have_class("active")
        expect(results).to_have_attribute("data-layout", "text")
        p.locator("#groupBy").check()
        p.reload()
        expect(p.locator("#groupBy")).to_be_checked()
        p.locator("#search").fill("невозможныйзапрос")
        p.locator("#search").press("Enter")
        expect(p.locator(".empty")).to_be_visible()
        p.locator("button[data-remove=search]").click()
        expect(p.locator(".empty")).to_have_count(0)
        first = p.locator(".result .stamp").first
        key = first.get_attribute("data-open")
        first.click()
        item = next(i for i in self.items if i["id"] == key)
        self.assertTrue(p.locator("#detail iframe").get_attribute("src").endswith(f'?start={item["seconds"]}'))

    def test_grouped_search(self):
        p = self.page
        p.locator("#layouts [data-layout=text]").click()
        p.locator("#quick [data-query='Карма']").click()
        while p.locator("#more").is_visible():
            p.locator("#more").click()
        ids = p.locator(".result .primary").evaluate_all("buttons => buttons.map(b => b.dataset.open)")
        self.assertEqual(len(ids), 111)
        by_id = {i["id"]: i["video"] for i in self.items}
        video_order = list(dict.fromkeys(by_id[key] for key in ids))
        p.locator("#groupBy").check()
        while p.locator("#more").is_visible():
            p.locator("#more").click()
        grouped = p.locator(".result .primary").evaluate_all("buttons => buttons.map(b => b.dataset.open)")
        self.assertCountEqual(grouped, ids)
        self.assertEqual(list(dict.fromkeys(by_id[key] for key in grouped)), video_order)
        bookmark = p.locator(".result .bookmark").first
        bookmark.click()
        p.locator("#layouts [data-layout=list]").click()
        expect(p.locator(".result .bookmark").first).to_have_attribute("aria-pressed", "true")
        # Grouping and the material layout remain independent of the video tab.
        p.locator("#videos").click()
        expect(p.locator("#groupOption")).to_be_hidden()
        expect(p.locator("#results")).to_have_attribute("data-layout", "grid")

    def test_event_filters(self):
        p = self.page
        self.assertTrue(p.locator("#eventPanel").is_hidden())
        p.goto(self.url + "#cat=shelling")
        self.assertEqual(self.count(), 89)
        self.assertEqual(p.locator("#eventPeriod option").count(), 4)
        self.assertEqual(p.locator("#eventYear option").all_text_contents()[1:],
                         ["2026 (14)", "2025 (8)", "2024 (1)"])
        p.clock.set_system_time("2025-05-01T12:00:00Z")
        p.locator("#eventPeriod").select_option("current")
        self.assertEqual(self.count(), 8)
        p.locator("#eventPeriod").select_option("previous")
        self.assertEqual(self.count(), 1)
        p.locator("#eventPeriod").select_option("year")
        p.locator("#eventYear").select_option("2026")
        p.locator("#cityMenu summary").click()
        p.locator("#citySearch").fill("Odessa")
        expect(p.locator("#cityList label")).to_have_count(1)
        self.assertEqual(p.locator("#cityList small").inner_text(), "7")
        p.locator("#cityList input").check()
        self.assertEqual(self.count(), 7)
        p.locator("#citySearch").fill("Kyiv")
        self.assertEqual(p.locator("#cityList small").inner_text(), "9")
        p.locator("#cityList input").check()
        self.assertEqual(self.count(), 11)
        self.assertEqual(p.locator("#eventYear option").all_text_contents()[1:],
                         ["2026 (11)", "2025 (6)", "2024 (0)"])
        p.locator("#citySearch").fill("")
        labels = p.locator("#cityList label").all_text_contents()
        self.assertFalse(any("область" in label or "Донбасс" in label for label in labels))
        p.locator("#citySearch").press("Escape")
        expect(p.locator("#citySearch")).to_be_hidden()
        p.locator("#sort").select_option("event-old")
        p.reload()
        self.assertEqual(self.count(), 11)
        self.assertEqual(p.locator("#sort").input_value(), "event-old")
        p.locator("[data-remove='city:Одесса']").click()
        self.assertEqual(self.count(), 9)
        p.locator("#eventReset").click()
        self.assertEqual(self.count(), 89)
        p.locator("#search").fill("Одесса")
        p.locator("#search").press("Enter")
        p.locator("#results [data-event-place='Одесса']").first.click()
        self.assertEqual(p.locator("#search").input_value(), "Одесса")
        self.assertIn("cat=shelling", p.url)
        p.locator("#eventReset").click()
        self.assertEqual(p.locator("#search").input_value(), "Одесса")
        p.locator("#clear").click()
        p.locator("#eventPeriod").select_option("previous")
        p.locator("#categories [data-cat='mobilization']").click()
        self.assertEqual(self.count(), 44)
        expect(p.locator("#eventPanel")).to_be_hidden()
        self.assertEqual(p.locator("#sort option").count(), 3)
        p.go_back()
        expect(p.locator("#eventPanel")).to_be_visible()
        self.assertEqual(self.count(), 1)
        p.locator("#videos").click()
        expect(p.locator("#eventPanel")).to_be_hidden()
        p.locator("#fragments").click()
        self.assertEqual(self.count(), 89)

    def test_event_dates_from_related_materials(self):
        p = self.page
        p.clock.set_system_time("2026-11-28T12:00:00Z")
        p.goto(self.url + "#cat=shelling&period=current")
        self.assertEqual(self.count(), 14)
        results = p.locator("#results .result")
        continuation = results.filter(has=p.locator('[data-bookmark="v001-t000882"]'))
        expect(continuation.locator(".event-date")).to_contain_text("ноябрь")
        continuation.get_by_role("button", name="Источник даты").click()
        self.assertIn("с 18 по 22 ноября 2026", p.locator("#detail h2").text_content())
        p.locator("#close").click()
        # In the January 2026 release this chapter names a city, but no event year.
        expect(p.locator('[data-bookmark="v050-t000870"]')).to_have_count(0)
        p.goto(self.url + "#cat=shelling&period=year&year=2025")
        cross_reference = p.locator(".result").filter(has=p.locator('[data-bookmark="v085-t000478"]'))
        cross_reference.get_by_role("button", name="Источник даты").click()
        expect(p.locator("#detail")).to_contain_text("17 и 20 июня 2025 года")

    def test_event_sort_and_groups(self):
        p = self.page
        p.goto(self.url + "#cat=shelling")
        known = {"v001-t000436", "v002-t001140", "v003-t000548", "v016-t000281",
                 "v017-t000400", "v017-t001825", "v018-t000103", "v026-t003021",
                 "v026-t004309", "v053-t002325", "v066-t001319", "v068-t000535",
                 "v069-t000344", "v094-t000398", "v127-t008494", "v084-full", "v086-full",
                 "v001-t000882", "v001-t001314", "v001-t001813", "v002-t001451",
                 "v017-t002440", "v085-t000478"}
        for order, first in (("event-new","v001-t000882"), ("event-old","v127-t008494")):
            p.locator("#sort").select_option(order)
            ids = p.locator(".result .primary").evaluate_all("bs => bs.map(b => b.dataset.open)")
            self.assertEqual(ids[0], first)
            self.assertEqual(set(ids[:len(known)]), known)
        p.locator("#sort").select_option("city-asc")
        self.assertIn("Белгород-Днестровский",p.locator(".result").first.text_content())
        p.locator("#sort").select_option("city-desc")
        self.assertIn("Херсон",p.locator(".result").first.text_content())
        for grouping in ("video","year","date","city"):
            p.locator("#eventGroup").select_option(grouping)
            for layout in ("grid","text","list"):
                p.locator(f"#layouts [data-layout={layout}]").click()
                self.assertGreater(p.locator(".video-group").count(), 0)
                if layout == "text":
                    self.assertEqual(p.locator("#results img").count(), 0)
            p.locator("#collapseAll").click()
            self.assertEqual(p.locator(".video-group[open]").count(), 0)
            p.locator("#expandAll").click()
            self.assertGreater(p.locator(".video-group[open]").count(), 0)
        while p.locator("#more").is_visible():
            p.locator("#more").click()
        key="v001-t000436"
        copies=p.locator(f'[data-bookmark="{key}"]')
        self.assertEqual(copies.count(),5)
        copies.first.click()
        self.assertEqual(p.locator(f'[data-bookmark="{key}"][aria-pressed=true]').count(),5)
        self.assertEqual(self.count(),89)
        p.locator("#results [data-event-place='Одесса']").first.click()
        self.assertEqual(p.locator(".video-group").count(),1)
        self.assertEqual(p.locator(".video-group summary strong").inner_text(),"Одесса")
        p.goto(self.url+"#cat=shelling&group=year")
        expect(p.locator("#eventGroup")).to_have_value("year")
        self.assertIn("Дата события не установлена",p.locator(".video-group summary").last.inner_text())
        self.assertEqual(p.evaluate("eventInterval('2025-12/2026-01')"),
                         {"start":"2025-12-01","end":"2026-01-31"})
        self.assertEqual(p.evaluate("eventInterval('2024-02')")["end"],"2024-02-29")
        self.assertEqual(p.evaluate("[...yearsCovered([eventInterval('2025-12/2026-01')])]"),[2025,2026])
        self.assertEqual(p.evaluate("[...yearsCovered([eventInterval('2024'),eventInterval('2026')])]"),[2024,2026])
        self.assertIn("день не установлен",p.evaluate("eventLabel('2025-12')"))


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
                             f'https://www.youtube-nocookie.com/embed/{v["id"]}')
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
