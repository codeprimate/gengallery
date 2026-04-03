"""Tests for gallery media timeline (prev/next across images and videos)."""

import unittest

from gengallery.services.generator import build_gallery_media_timeline, neighbors_in_timeline


class TestGalleryMediaTimeline(unittest.TestCase):
    def test_merges_and_sorts_by_exif_date_newest_first(self):
        gallery = {
            "images": [
                {
                    "id": "img_old",
                    "url": "/a/old.html",
                    "exif": {"DateTimeOriginal": "2020:01:01 12:00:00"},
                },
                {
                    "id": "img_new",
                    "url": "/a/new.html",
                    "exif": {"DateTimeOriginal": "2024:06:01 10:00:00"},
                },
            ],
            "videos": [
                {
                    "id": "vid_mid",
                    "media_type": "video",
                    "url": "/a/mid.html",
                    "exif": {"DateTimeOriginal": "2022:01:01 00:00:00"},
                }
            ],
        }
        tl = build_gallery_media_timeline(gallery)
        self.assertEqual([x["id"] for x in tl], ["img_new", "vid_mid", "img_old"])

    def test_neighbors_span_image_to_video(self):
        gallery = {
            "images": [
                {
                    "id": "i1",
                    "url": "/g/i1.html",
                    "exif": {"DateTimeOriginal": "2024:01:01 00:00:00"},
                },
            ],
            "videos": [
                {
                    "id": "v1",
                    "media_type": "video",
                    "url": "/g/v1.html",
                    "exif": {"DateTimeOriginal": "2023:01:01 00:00:00"},
                }
            ],
        }
        tl = build_gallery_media_timeline(gallery)
        prev_i, next_i = neighbors_in_timeline(tl, "i1")
        self.assertIsNone(prev_i)
        self.assertEqual(next_i["id"], "v1")

        prev_v, next_v = neighbors_in_timeline(tl, "v1")
        self.assertEqual(prev_v["id"], "i1")
        self.assertIsNone(next_v)


if __name__ == "__main__":
    unittest.main()
