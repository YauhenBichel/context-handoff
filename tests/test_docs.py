import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://yauhenbichel.github.io/context-handoff/"


class DocsSite(unittest.TestCase):
    """The README and the GitHub Pages site in docs/ point at files that exist."""

    def test_readme_local_images_exist(self):
        for path in re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", (ROOT / "README.md").read_text()):
            if not path.startswith("http"):
                self.assertTrue((ROOT / path).is_file(), path)

    def test_index_local_assets_exist(self):
        html = (ROOT / "docs/index.html").read_text()
        for path in re.findall(r'src="([^":]+)"', html):
            self.assertTrue((ROOT / "docs" / path).is_file(), path)
        self.assertIn(f'<link rel="canonical" href="{SITE}">', html)

    def test_sitemap_lists_only_existing_pages(self):
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locs = [e.text for e in ET.parse(ROOT / "docs/sitemap.xml").findall("s:url/s:loc", ns)]
        self.assertIn(SITE, locs)
        for loc in locs:
            self.assertTrue(loc.startswith(SITE), loc)
            rel = loc[len(SITE):] or "index.html"
            self.assertTrue((ROOT / "docs" / rel).is_file(), loc)


if __name__ == "__main__":
    unittest.main()
