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
PAYLOAD = re.compile(r"window\.RAMA_DB = (.*);\s*", re.S)


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
        catalog_url = self.page.locator('script[src$="/catalog.js"]').evaluate("s => s.src")
        self.payload = PAYLOAD.fullmatch(self.page.request.get(catalog_url).text())[1]

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
        p.locator("#search").fill("Карма")
        p.locator("#search").press("Enter")
        while p.locator("#more").is_visible():
            p.locator("#more").click()
        ids = p.locator(".result .primary").evaluate_all("buttons => buttons.map(b => b.dataset.open)")
        self.assertEqual(len(ids), 113)
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
                         ["2026 (34)", "2025 (49)", "2024 (6)"])
        p.clock.set_system_time("2025-05-01T12:00:00Z")
        p.locator("#eventPeriod").select_option("current")
        self.assertEqual(self.count(), 49)
        p.locator("#eventPeriod").select_option("previous")
        self.assertEqual(self.count(), 6)
        p.locator("#eventPeriod").select_option("year")
        p.locator("#eventYear").select_option("2026")
        p.locator("#cityMenu summary").click()
        p.locator("#citySearch").fill("Odessa")
        expect(p.locator("#cityList label")).to_have_count(1)
        self.assertEqual(p.locator("#cityList small").inner_text(), "7")
        p.locator("#cityList input").check()
        self.assertEqual(self.count(), 7)
        p.locator("#citySearch").fill("Kyiv")
        self.assertEqual(p.locator("#cityList small").inner_text(), "13")
        p.locator("#cityList input").check()
        self.assertEqual(self.count(), 15)
        self.assertEqual(p.locator("#eventYear option").all_text_contents()[1:],
                         ["2026 (15)", "2025 (20)", "2024 (2)"])
        p.locator("#citySearch").fill("")
        labels = p.locator("#cityList label").all_text_contents()
        self.assertFalse(any("область" in label or "Донбасс" in label for label in labels))
        p.locator("#citySearch").press("Escape")
        expect(p.locator("#citySearch")).to_be_hidden()
        p.locator("#sort").select_option("event-old")
        p.reload()
        self.assertEqual(self.count(), 15)
        self.assertEqual(p.locator("#sort").input_value(), "event-old")
        p.locator("[data-remove='city:Одесса']").click()
        self.assertEqual(self.count(), 13)
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
        self.assertEqual(self.count(), 6)
        p.locator("#videos").click()
        expect(p.locator("#eventPanel")).to_be_hidden()
        p.locator("#fragments").click()
        self.assertEqual(self.count(), 89)

    def test_event_dates_from_related_materials(self):
        p = self.page
        p.clock.set_system_time("2026-11-28T12:00:00Z")
        p.goto(self.url + "#cat=shelling&period=current")
        self.assertEqual(self.count(), 34)
        results = p.locator("#results .result")
        continuation = results.filter(has=p.locator('[data-bookmark="v001-t000882"]'))
        expect(continuation.locator(".event-date")).to_contain_text("ноября")
        continuation.get_by_role("button", name="Источник даты").click()
        self.assertIn("с 18 по 22 ноября 2026", p.locator("#detail h2").text_content())
        p.locator("#close").click()
        p.locator("#more").click()
        january = results.filter(has=p.locator('[data-bookmark="v050-t000870"]'))
        expect(january.locator(".event-date")).to_have_text("2026 год · предположительный год по публикации видео")
        p.goto(self.url + "#cat=shelling&period=year&year=2025")
        expect(p.locator("#eventYear")).to_have_value("2025")
        while p.locator("#more").is_visible():
            p.locator("#more").click()
        cross_reference = p.locator(".result").filter(has=p.locator('[data-bookmark="v085-t000478"]'))
        cross_reference.get_by_role("button", name="Источник даты").click()
        expect(p.locator("#detail")).to_contain_text("17 и 20 июня 2025 года")

    def test_documented_date_precedes_publication_year(self):
        result = self.page.evaluate("""() => {
          const records = db.items.filter(i => ['v001-t000436','v050-t000870'].includes(i.id));
          const videoDates = new Map(records.map(i => [i.video,{date:'2024-01-01'}]));
          const index = createShellingIndex(records, videoDates).metadata;
          return records.map(i => [i.id,index.get(i.id).spec,index.get(i.id).inferred]);
        }""")
        self.assertCountEqual(result,[["v001-t000436","2026-11-18/2026-11-22",False],
                                      ["v050-t000870","2024",True]])

    def test_event_sort_and_groups(self):
        p = self.page
        p.goto(self.url + "#cat=shelling")
        for order in ("event-new","event-old"):
            p.locator("#sort").select_option(order)
            while p.locator("#more").is_visible():
                p.locator("#more").click()
            ids = p.locator(".result .primary").evaluate_all("bs => bs.map(b => b.dataset.open)")
            self.assertEqual(len(set(ids)), 89)
            # A 2026 dated news block and an older 2024 event retain their relative order.
            newer = ids.index("v001-t000436")
            older = ids.index("v127-t008494")
            self.assertEqual(newer < older, order == "event-new")
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
        self.assertEqual(p.locator(".video-group summary strong").all_text_contents(), ["2026","2025","2024"])
        self.assertEqual(p.evaluate("eventInterval('2025-12/2026-01')"),
                         {"start":"2025-12-01","end":"2026-01-31"})
        self.assertEqual(p.evaluate("eventInterval('2024-02')")["end"],"2024-02-29")
        self.assertEqual(p.evaluate("[...yearsCovered([eventInterval('2025-12/2026-01')])]"),[2025,2026])
        self.assertEqual(p.evaluate("[...yearsCovered([eventInterval('2024'),eventInterval('2026')])]"),[2024,2026])
        self.assertIn("день не установлен",p.evaluate("eventLabel('2025-12')"))


    def test_inventory(self):
        self.assertEqual(hashlib.sha256(self.payload.encode()).hexdigest(),
                         "8de3dc41f30d17bd4ba91db0f9e34ee28919f3d7ac4aeabb4a3bbb6fd7656156")
        d = self.db
        for key in ("sections", "categories", "videos", "items"):
            self.assertEqual(len(d[key]), len({row["id"] for row in d[key]}))
        videos = {v["id"] for v in d["videos"]}
        cats = {c["id"] for c in d["categories"]}
        self.assertEqual(len(videos), 141)
        self.assertEqual(sum(i["seconds"] is not None for i in self.items), 2099)
        self.assertEqual(sum(len(i["cats"]) for i in self.items), 3522)
        self.assertEqual(sum(len(v["references"]) for v in d["videos"]), 80)
        self.assertEqual(sum(len(v["descriptions"]) for v in d["videos"]), 136)
        for i in self.items:
            self.assertIn(i["video"], videos)
            self.assertTrue(set(i["cats"]) <= cats)
            self.assertEqual(len(i["cats"]), len(set(i["cats"])))
            self.assertTrue(i["seconds"] is None or isinstance(i["seconds"], int) and i["seconds"] >= 0)

    def test_reviewed_topic_memberships(self):
        # Fingerprint of the v6 public export, excluding only the reviewed memberships.
        base = json.loads(self.payload)
        for item in base["items"]:
            del item["cats"]
        raw = json.dumps(base, ensure_ascii=False, separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         "05a89ca3b080896c6ed7abeeeb935780b1aa4aa3dccc07b39ad1eda1559a07df")
        p = self.page
        expected_topics = {
            "v001-t010221": "abuse",       # Показания учеников гурукулы
            "v001-t005565": "sannyasa",    # Возвращение в санньясу
            "v002-t006140": "governance",  # План GBC
            "v005-t007759": "propaganda",  # Тезисы Тарун Кришна даса
        }
        p.goto(self.url + "#cat=science")
        while p.locator("#more").is_visible():
            p.locator("#more").click()
        science = set(p.locator("#results .primary").evaluate_all("bs=>bs.map(b=>b.dataset.open)"))
        self.assertEqual(len(science), 44)
        self.assertTrue(science.isdisjoint(expected_topics))
        self.assertTrue({"v025-t000198","v001-t002763","v025-t000274"} <= science)
        by_id = {i["id"]: i for i in self.items}
        news = {i["id"] for i in self.items if i["type"] != "service" and not i["cats"]}
        self.assertEqual(news, {"v106-t000788", "v108-t001537"})
        for key in news:
            p.goto(self.url)
            p.locator("#search").fill(by_id[key]["title"])
            p.locator("#search").press("Enter")
            expect(p.locator(f'#results .primary[data-open="{key}"]')).to_be_visible()
        for key, topic in expected_topics.items():
            self.assertIn(topic, by_id[key]["cats"])
        self.assertEqual(by_id["v076-t000259"]["cats"], ["astrology"])
        self.assertNotIn("military", by_id["v008-t002957"]["cats"])
        self.assertNotIn("interfaith", by_id["v133-t004255"]["cats"])

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
        p.locator('#quick a[href="#cat=war-seminar"]').click()
        p.go_back()
        self.assertEqual(self.count(), 2005)
        p.go_forward()
        self.assertLess(self.count(), 2005)
        p.locator("#clearFilters").click()
        self.assertEqual(self.count(), 2005)
        self.assertEqual(p.locator("#kind option").evaluate_all("opts => opts.map(o=>o.value)"), ["all","fragment","video"])
        p.locator("#kind").select_option("all")
        for order in ("old", "new"):
            p.locator("#sort").select_option(order)
            dates = p.locator(".result .meta").all_text_contents()
            dates = [re.search(r"\d{4}-\d{2}-\d{2}$", s)[0] for s in dates]
            self.assertEqual(dates, sorted(dates, reverse=order == "new"))
        p.locator("#search").fill("Карма")
        p.locator("#search").press("Enter")
        self.assertEqual(self.count(), 113)
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
        self.assertIn("Центр изучения варнашрамы «Рама»", p.title())
        self.assertTrue(p.locator("meta[name=description]").get_attribute("content"))
        self.assertEqual(p.locator("link[rel=canonical]").get_attribute("href"), "https://liubomirt-dharma.github.io/rama-db/")
        for width,height in ((320,568),(360,800),(375,812),(390,844),(412,915),(430,932),(768,1024),(820,1180),(1024,768),(1180,820),(1366,768),(1440,900),(1920,1080)):
            p.set_viewport_size({"width": width, "height": height})
            self.assertLessEqual(p.evaluate("document.documentElement.scrollWidth"), width)
            self.assertTrue(p.locator(".logo").evaluate("""logo => {
                const text = document.createRange();
                text.selectNodeContents(logo);
                const bounds = text.getBoundingClientRect(), box = logo.getBoundingClientRect();
                return !box.width || bounds.top >= box.top && bounds.bottom <= box.bottom;
            }"""))
            if width <= 850:
                button = p.locator("#mobileCategories")
                button.click()
                p.locator('#categories [data-section-select="war"]').click()
                self.assertEqual(button.get_attribute("aria-expanded"), "false")

    def test_complete_video_filter(self):
        p = self.page
        all_ids = {v["id"] for v in self.db["videos"]}

        def ids():
            while p.locator("#more").is_visible():
                p.locator("#more").click()
            rows = p.locator(".record-info").evaluate_all("ds=>ds.map(d=>d.dataset.record)")
            self.assertEqual(len(rows), len(set(rows)))
            self.assertEqual(len(rows), self.count())
            return set(rows)

        for old_type in ("overview", "service"):
            p.goto(self.url + "#kind=" + old_type)
            expect(p.locator("#kind")).to_have_value("all")
            self.assertNotIn("kind=", p.url)
        p.locator("#kind").select_option("video")
        self.assertEqual(ids(), all_ids)
        p.locator("#categories [data-cat=mobilization]").click()
        expected = {i["video"] for i in self.items if "mobilization" in i["cats"]}
        self.assertEqual(ids(), expected)
        p.goto(self.url + "#cat=shelling&period=year&year=2025&city=Одесса")
        while p.locator("#more").is_visible():
            p.locator("#more").click()
        keys = p.locator("#results .primary").evaluate_all("bs=>bs.map(b=>b.dataset.open)")
        p.locator("#kind").select_option("video")
        self.assertEqual(ids(), {i["video"] for i in self.items if i["id"] in keys})
        p.locator("#search").fill("xyz123")
        p.locator("#search").press("Enter")
        self.assertEqual(self.count(), 0)
        p.locator("#allVideos").click()
        self.assertEqual(ids(), all_ids)
        self.assertEqual(p.locator("#sort").input_value(), "new")
        self.assertEqual(p.locator("#search").input_value(), "")
        self.assertEqual(p.locator("#activeFilters button").count(), 0)
        self.assertIn("Все видео", p.title())
        dates = p.locator(".video-record .meta").all_text_contents()
        self.assertEqual(dates, sorted(dates, key=lambda d:d[:10], reverse=True))
        p.locator("#search").fill("дхарма")
        p.locator("#search").press("Enter")
        self.assertGreater(self.count(), 0)
        self.assertLess(self.count(), len(all_ids))
        p.reload()
        self.assertEqual(p.locator("#search").input_value(), "дхарма")

    def test_lazy_video_disclosures(self):
        p = self.page
        p.locator("#allVideos").click()
        cards = p.locator(".video-record")
        first, second = cards.nth(0), cards.nth(1)
        self.assertEqual(p.locator(".record-content,.record-info[open]").count(), 0)
        first.locator("summary").click()
        second.locator("summary").click()
        expect(p.locator(".record-content")).to_have_count(2)
        video = first.locator("details").get_attribute("data-record")
        items = [i for i in self.items if i["video"] == video]
        self.assertEqual(first.locator(".record-content .chapter").count(), len(items))
        src = next(v for v in self.db["videos"] if v["id"] == video)
        for d in src["descriptions"]:
            self.assertIn(d.strip(), first.inner_text())
        self.assertEqual(len(src["references"]), first.locator(".record-content a").count())
        button = first.locator(".chapter button").first
        item = next(i for i in items if i["id"] == button.get_attribute("data-open"))
        button.click()
        self.assertTrue(p.locator("#detail iframe").get_attribute("src").endswith(f'?start={item["seconds"]}'))
        p.keyboard.press("Escape")
        first.locator("summary").click()
        expect(second.locator(".record-content")).to_be_visible()
        p.locator("#expandAll").click()
        expect(p.locator(".record-content")).to_have_count(24)
        p.locator("#more").click()
        expect(p.locator(".record-content")).to_have_count(48)
        p.locator("#collapseAll").click()
        expect(p.locator(".record-content")).to_have_count(0)
        first.locator("summary").click()
        p.locator("#allVideos").click()
        expect(p.locator(".record-info[open]")).to_have_count(0)

    def test_touch_navigation_and_shortcuts(self):
        p = self.page
        for link in p.locator("#quick a").all():
            href = link.get_attribute("href")
            link.click()
            if "directory" in href:
                expect(p.locator("#peopleDirectory")).to_be_visible()
                p.go_back()
            else:
                self.assertGreater(self.count(), 0)
                expect(link).to_have_attribute("aria-current", "page")
                self.assertIn(href[1:], p.url)
        p.set_viewport_size({"width": 375, "height": 812})
        p.locator("#mobileCategories").click()
        expect(p.locator("#topicDrawer")).to_be_visible()
        p.keyboard.press("Escape")
        expect(p.locator("#mobileCategories")).to_be_focused()
        p.locator("#mobileSearch").click()
        expect(p.locator("#search")).to_be_focused()
        p.locator("#allVideos").click()
        p.locator("#filterToggle").click()
        p.locator("#sort").select_option("old")
        p.locator("#mobileSaved").click()
        expect(p.locator("#heading")).to_have_text("Избранное")
        p.locator("#mobileHome").click()
        expect(p.locator("#heading")).to_have_text("Все материалы")
        p.locator("#filterToggle").click()
        expect(p.locator("#filterFields")).to_be_hidden()
        p.locator("#quick a[href='#cat=shelling']").click()
        expect(p.locator("#filterToggle")).to_have_text("Фильтры · 1")
        expect(p.locator("#heading")).to_be_in_viewport()

    def test_large_text_phone(self):
        p = self.page
        p.set_viewport_size({"width":320, "height":568})
        p.evaluate("""() => {
          const elements = [...document.body.querySelectorAll('*:not(script):not(style)')];
          const sizes = elements.map(el=>parseFloat(getComputedStyle(el).fontSize)*2);
          elements.forEach((el,i)=>el.style.fontSize=sizes[i]+'px');
        }""")
        self.assertEqual(p.evaluate("document.documentElement.scrollWidth"), 320)
        expect(p.locator("#allVideos")).to_be_in_viewport()
        p.locator("#mobileCategories").click()
        expect(p.locator("#drawerClose")).to_be_focused()
        self.assertTrue(p.locator("#topicDrawer").evaluate("d=>d.scrollWidth<=d.clientWidth"))

    def test_phone_landscape_touch(self):
        context = self.browser.new_context(viewport={"width":932,"height":430}, is_mobile=True, has_touch=True)
        self.addCleanup(context.close)
        p = context.new_page()
        origin = urlsplit(self.url).netloc
        p.route("**/*", lambda r:r.continue_() if urlsplit(r.request.url).netloc == origin else r.abort())
        p.goto(self.url)
        p.locator("#mobileCategories").tap()
        p.locator("#categories [data-cat=shelling]").tap()
        expect(p.locator("#heading")).to_have_text("Обстрелы Украины")
        expect(p.locator("#topicDrawer")).to_be_hidden()
        expect(p.locator("#categoryPanel")).to_be_hidden()
        p.locator("#allVideos").tap()
        expect(p.locator("#results")).to_have_attribute("data-layout","list")
        self.assertEqual(p.evaluate("document.documentElement.scrollWidth"), 932)
