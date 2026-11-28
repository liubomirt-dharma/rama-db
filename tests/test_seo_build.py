"""Check publication changes without live YouTube or owner verification credentials."""
from contextlib import redirect_stdout
from io import BytesIO, StringIO
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from scripts import build_seo as seo


class BuildUpdates(unittest.TestCase):
    def test_new_and_removed_material_and_verified_cover(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "site"
            (root / "assets/video-covers").mkdir(parents=True)
            shutil.copy(seo.ROOT / "index.html",root/"index.html")
            vid = "sampleVideo"
            data = {
                "sections":[{"id":"example","name":"Раздел"}],
                "categories":[{"id":"next-seminar","section":"example","parent":"","active":True,"name":"Семинар"}],
                "videos":[{"id":vid,"title":"Выпуск","date":"2026-01-01","number":1,
                           "references":[],"descriptions":["Описание"]}],
                "items":[{"id":"chapter-1","video":vid,"seconds":0,"cats":["next-seminar"],"type":"fragment","title":"Глава"}],
            }
            def rebuild():
                (root / "assets/catalog.js").write_text("window.RAMA_DB = "+json.dumps(data)+";\n")
                with patch.object(seo,"ROOT",root), redirect_stdout(StringIO()):
                    seo.build(out)
            # The verified cache is copied to the new build and used consistently by OG and Schema.
            shutil.copy(seo.ROOT/"assets/social-cover.jpg",root/"assets/video-covers"/(vid+".jpg"))
            rebuild()
            seminar = out/"seminars/next-seminar/index.html"
            watch = out/"video"/vid/"index.html"
            image = seo.BASE+"assets/video-covers/"+vid+".jpg"
            self.assertIn(f'property="og:image" content="{image}"',seminar.read_text())
            self.assertIn(f'"thumbnailUrl":"{image}"',watch.read_text())
            self.assertIn(seo.BASE+"seminars/next-seminar/",(out/"sitemap.xml").read_text())
            data["videos"][0]["title"]="Новое название"
            rebuild()
            self.assertIn("Новое название",watch.read_text())
            data["items"].clear()
            data["videos"].clear()
            rebuild()
            self.assertFalse(seminar.exists())
            self.assertFalse(watch.exists())
            self.assertFalse((out/"assets/video-covers"/(vid+".jpg")).exists())
            self.assertNotIn(vid,(out/"sitemap.xml").read_text())

    def test_thumbnail_validation(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is used only for the optional YouTube cover fetch")
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for size, expected in [((480,360),True),((120,90),False)]:
                response = BytesIO()
                Image.new("RGB",size).save(response,format="JPEG")
                response.seek(0)
                with patch.object(seo,"urlopen",return_value=response):
                    self.assertEqual(seo.get_thumbnail(("example",folder)),expected)
                self.assertEqual((folder/"example.jpg").exists(),expected)
