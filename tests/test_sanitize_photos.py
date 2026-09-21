import io
import subprocess
import sys

import numpy as np
from helpers import ROOT, ScriptTestCase
from PIL import Image, PngImagePlugin


class SanitizeTests(ScriptTestCase):
    def setUp(self):
        super().setUp()
        self.sanitizer = self.load("sanitize_photos")

    def test_jpeg_metadata_and_trailer_removed_without_recompression(self):
        for progressive, mode in [(False, "RGB"), (True, "RGB"), (False, "CMYK")]:
            with self.subTest(progressive=progressive, mode=mode):
                source = self.root / "original.jpg"
                destination = self.root / "clean.jpg"
                exif = Image.Exif()
                exif[271] = "Test camera"
                exif[274] = 1
                exif[34853] = {1: "N", 2: (1.0, 2.0, 3.0)}
                im = Image.fromarray(
                    np.random.default_rng(1).integers(0, 256, (32, 40, 3), dtype=np.uint8)
                )
                im.convert(mode).save(
                    source, exif=exif, progressive=progressive, comment=b"private comment"
                )
                source.write_bytes(source.read_bytes() + b"private trailer")
                before = source.read_bytes()
                size = self.sanitizer.sanitize(source, destination)
                self.assertEqual(source.read_bytes(), before)
                self.assertEqual(size, destination.stat().st_size)
                self.assertNotIn(b"private", destination.read_bytes())
                with Image.open(source) as original, Image.open(destination) as clean:
                    np.testing.assert_array_equal(
                        np.array(original.convert("RGBA")), np.array(clean.convert("RGBA"))
                    )
                    self.assertFalse(clean.getexif())
                    self.assertFalse(
                        {"exif", "comment", "xmp", "icc_profile", "dpi"} & clean.info.keys()
                    )

    def test_png_text_removed_and_alpha_preserved(self):
        source, destination = self.root / "original.png", self.root / "clean.png"
        pixels = np.random.default_rng(2).integers(0, 256, (12, 15, 4), dtype=np.uint8)
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("Location", "private")
        Image.fromarray(pixels).save(source, pnginfo=metadata)
        self.sanitizer.sanitize(source, destination)
        with Image.open(destination) as clean:
            np.testing.assert_array_equal(np.array(clean), pixels)
            self.assertFalse(clean.info)

    def test_original_cannot_be_overwritten(self):
        source = self.root / "source.png"
        Image.new("RGB", (4, 4)).save(source)
        before = source.read_bytes()
        with self.assertRaisesRegex(ValueError, "differ"):
            self.sanitizer.sanitize(source, source)
        self.assertEqual(source.read_bytes(), before)

    def test_rotated_photo_rejected_before_export(self):
        source, destination = self.root / "rotated.jpg", self.root / "clean.jpg"
        exif = Image.Exif()
        exif[274] = 6
        Image.new("RGB", (8, 12)).save(source, exif=exif)
        with self.assertRaisesRegex(ValueError, "orientation"):
            self.sanitizer.sanitize(source, destination)
        self.assertFalse(destination.exists())

    def test_malformed_jpeg_rejected(self):
        for data in (b"not jpeg", b"\xff\xd8", b"\xff\xd8\xff", b"\xff\xd8\xff\xe1\x00\x10short"):
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.sanitizer.clean_jpeg(data)
        buffer = io.BytesIO()
        Image.new("RGB", (8, 8)).save(buffer, format="JPEG")
        with self.assertRaises(ValueError):
            self.sanitizer.clean_jpeg(buffer.getvalue()[:-1])

    def test_cli_exports_only_supported_images(self):
        source = self.root / "images"
        Image.new("RGB", (8, 8)).save(source / "photo.JPG")
        (source / "README.md").write_text("Skip this")
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/sanitize_photos.py"),
                str(source),
                str(self.root / "export"),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Exported 1 images", result.stdout)
        self.assertEqual([p.name for p in (self.root / "export").iterdir()], ["photo.JPG"])
