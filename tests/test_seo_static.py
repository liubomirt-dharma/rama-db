"""Validate the files actually served by Pages, without running JavaScript."""
import json
import os
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
import unittest
from urllib.parse import parse_qs, urljoin, urlsplit
import xml.etree.ElementTree as ET

BASE = "https://liubomirt-dharma.github.io/rama-db/"
ROOT = Path(os.environ.get("RAMA_SEO_ROOT", Path(__file__).resolve().parents[1])).resolve()


class Document(HTMLParser):
    def __init__(self, path):
        super().__init__()
        self.tags = {}
        self.graph = []
        self.title = ""
        self.ids = set()
        self.links = []
        self.files = []
        self.headings = []
        self.capture = ""
        self.text = []
        self.chapters = {}
        self.feed(path.read_text())

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "meta":
            self.tags[a.get("name") or a.get("property")] = a.get("content")
        if tag == "link" and a.get("rel") == "canonical":
            self.canonical = a["href"]
        if tag == "link" and a.get("rel") in ("stylesheet", "apple-touch-icon", "icon"):
            self.files.append(a["href"])
        if tag in ("script","img") and a.get("src"):
            self.files.append(a["src"])
        if tag == "img" and "alt" not in a:
            raise AssertionError("Missing image alt attribute")
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag == "li" and "data-seconds" in a:
            self.chapters[int(a["data-seconds"])] = a["id"]
        if tag in ("h1","title") or tag == "script" and a.get("type") == "application/ld+json":
            self.capture = tag
            self.text = []

    def handle_data(self, data):
        if self.capture:
            self.text.append(data)

    def handle_endtag(self, tag):
        if self.capture != tag:
            return
        value = "".join(self.text)
        if tag == "script":
            self.graph = json.loads(value)["@graph"]
        elif tag == "title":
            self.title = value
        else:
            self.headings.append(value)
        self.capture = ""


@lru_cache(maxsize=None)
def document(route):
    return Document(ROOT / route / "index.html")


class StaticSeo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        script = (ROOT / "assets/catalog.js").read_text().strip()
        cls.db = json.loads(script.removeprefix("window.RAMA_DB = ").removesuffix(";"))
        cls.topics = {c["id"] for c in cls.db["categories"] if c["active"] and
                      any(c["id"] in i["cats"] for i in cls.db["items"] if i["type"] != "service")}
        cls.urls = [node.text for node in ET.parse(ROOT/"sitemap.xml").iterfind(".//{*}loc")]

    def test_sitemap_and_metadata(self):
        expected = {"", "videos/", "topics/"}
        expected.update("video/"+v["id"]+"/" for v in self.db["videos"])
        expected.update(("seminars/" if "seminar" in c.split("-") else "topics/")+c+"/" for c in self.topics)
        expected.update("sections/"+s["id"]+"/" for s in self.db["sections"]
                        if any(c["section"]==s["id"] and c["id"] in self.topics for c in self.db["categories"]))
        self.assertCountEqual(self.urls,[BASE+route for route in expected])
        titles, descriptions = [], []
        reachable = {""}
        pending = [""]
        while pending:
            route = pending.pop()
            for href in document(route).links:
                target = urlsplit(urljoin(BASE+route,href))
                dest = target.path.removeprefix("/rama-db/")
                if target.netloc==urlsplit(BASE).netloc and dest in expected and dest not in reachable:
                    reachable.add(dest)
                    pending.append(dest)
        self.assertEqual(reachable,expected)
        for url in self.urls:
            with self.subTest(url=url):
                route=url.removeprefix(BASE)
                doc=document(route)
                self.assertEqual(doc.lang,"ru")
                self.assertEqual(doc.canonical,url)
                self.assertEqual(doc.tags["og:url"],url)
                self.assertEqual(doc.tags["og:locale"],"ru_RU")
                self.assertIn("index",doc.tags["robots"].split(","))
                self.assertEqual(doc.tags["twitter:card"],"summary_large_image")
                for key in ("title","description","image","image:alt"):
                    self.assertTrue(doc.tags["og:"+key])
                    self.assertEqual(doc.tags["twitter:"+key],doc.tags["og:"+key])
                self.assertEqual(doc.tags["og:title"],doc.title)
                self.assertEqual(doc.tags["og:description"],doc.tags["description"])
                image = doc.tags["og:image"]
                self.assertTrue(image.startswith(BASE))
                self.assertTrue((ROOT/image.removeprefix(BASE)).is_file())
                self.assertEqual(doc.tags["og:image:secure_url"],image)
                self.assertGreater(int(doc.tags["og:image:width"]),0)
                self.assertGreater(int(doc.tags["og:image:height"]),0)
                self.assertTrue(doc.graph)
                self.assertTrue(doc.headings)
                if route:
                    self.assertEqual(len(doc.headings),1)
                titles.append(doc.title)
                descriptions.append(doc.tags["description"])
        self.assertEqual(len(titles),len(set(titles)))
        self.assertEqual(len(descriptions),len(set(descriptions)))
        self.assertIn("Sitemap: "+BASE+"sitemap.xml",(ROOT/"robots.txt").read_text())
        self.assertEqual(Document(ROOT/"404.html").tags["robots"],"noindex,follow")

    def test_internal_references(self):
        for url in self.urls:
            route=url.removeprefix(BASE)
            doc=document(route)
            for href in doc.files+doc.links:
                target = urlsplit(urljoin(url,href))
                if target.netloc != urlsplit(BASE).netloc:
                    continue
                self.assertTrue(target.path.startswith("/rama-db/"),href)
                dest=target.path.removeprefix("/rama-db/")
                if target.path.endswith("/"):
                    page=document(dest)
                    if target.fragment and not (dest=="" and "=" in target.fragment):
                        self.assertIn(target.fragment,page.ids)
                    if target.query:
                        self.assertIn(int(parse_qs(target.query)["t"][0]),page.chapters)
                else:
                    self.assertTrue((ROOT/dest).is_file(),href)

    def test_watch_and_clips(self):
        for v in self.db["videos"]:
            url=BASE+"video/"+v["id"]+"/"
            doc=document(url.removeprefix(BASE))
            if not v["date"]:
                self.assertFalse(any(n["@type"]=="VideoObject" for n in doc.graph))
                continue
            obj=next(n for n in doc.graph if n["@type"]=="VideoObject")
            self.assertEqual(obj["name"],v["title"])
            self.assertEqual(obj["embedUrl"],"https://www.youtube-nocookie.com/embed/"+v["id"])
            self.assertEqual(obj["uploadDate"],v["date"])
            source={i["seconds"]:i for i in self.db["items"] if i["video"]==v["id"] and i["seconds"] is not None}
            self.assertEqual(doc.chapters,{t:i["id"] for t,i in source.items()})
            times=sorted(source)
            expected=[(t,end) for t,end in zip(times,times[1:]) if source[t]["type"]!="service"]
            clips=obj.get("hasPart",[])
            self.assertEqual([(c["startOffset"],c["endOffset"]) for c in clips],expected)
            for clip in clips:
                sec=clip["startOffset"]
                self.assertEqual(clip["name"],source[sec]["title"])
                self.assertEqual(clip["url"],url+"?t="+str(sec))
