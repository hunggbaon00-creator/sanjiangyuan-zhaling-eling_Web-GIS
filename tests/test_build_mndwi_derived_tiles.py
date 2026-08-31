import hashlib
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from scripts.build_mndwi_derived_tiles import inventory_tiles, read_png_header, sha256_file


def png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + chunk_type
        + payload
        + struct.pack(">I", zlib.crc32(chunk_type + payload) & 0xFFFFFFFF)
    )


def make_rgba_png(path: Path, width: int = 256, height: int = 256) -> None:
    rows = b"".join(b"\x00" + b"\x00\x00\x00\x00" * width for _ in range(height))
    content = (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(rows))
        + png_chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


class DerivedTileBuildTests(unittest.TestCase):
    def test_hash_and_png_header(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tile.png"
            make_rgba_png(path)
            self.assertEqual(
                read_png_header(path),
                {"width": 256, "height": 256, "bit_depth": 8, "color_type": 6},
            )
            self.assertEqual(sha256_file(path), hashlib.sha256(path.read_bytes()).hexdigest())

    def test_inventory_requires_all_contract_zooms_and_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tile_root = Path(directory)
            for zoom in range(5, 14):
                make_rgba_png(tile_root / str(zoom) / "1" / "2.png")

            first = inventory_tiles(tile_root)
            second = inventory_tiles(tile_root)

            self.assertEqual(first, second)
            self.assertEqual(first["tile_count"], 9)
            self.assertEqual(first["counts_by_zoom"], {str(z): 1 for z in range(5, 14)})
            self.assertEqual(len(first["package_sha256"]), 64)

    def test_inventory_rejects_wrong_tile_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tile_root = Path(directory)
            make_rgba_png(tile_root / "5" / "1" / "2.png", width=128)
            with self.assertRaisesRegex(ValueError, "256像素"):
                inventory_tiles(tile_root)


if __name__ == "__main__":
    unittest.main()
