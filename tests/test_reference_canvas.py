"""The reference canvas must never become character silhouette evidence."""
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/ai3d'))
from score_candidate_renders import _normalize_view, _iou


class ReferenceCanvasTests(unittest.TestCase):
    def test_gray_inset_and_white_padding_do_not_change_silhouette(self):
        with tempfile.TemporaryDirectory() as tmp:
            reference = Image.new('RGBA', (128, 128), 'white')
            d = ImageDraw.Draw(reference)
            d.rectangle((24, 4, 103, 123), fill=(236, 236, 236, 255))
            d.ellipse((52, 12, 76, 36), fill=(20, 30, 40, 255))
            d.rectangle((48, 32, 80, 74), fill=(20, 30, 40, 255))
            d.rectangle((53, 38, 75, 68), fill='white')
            d.rectangle((49, 74, 60, 115), fill=(20, 30, 40, 255))
            d.rectangle((68, 74, 79, 115), fill=(20, 30, 40, 255))
            transparent = reference.copy()
            data = transparent.load()
            for y in range(128):
                for x in range(128):
                    if data[x, y][:3] == (236, 236, 236) or not (24 <= x <= 103 and 4 <= y <= 123):
                        data[x, y] = (0, 0, 0, 0)
            a, b = Path(tmp) / 'reference.png', Path(tmp) / 'candidate.png'
            reference.save(a)
            transparent.save(b)
            actual = _normalize_view(a, candidate=False)
            expected = _normalize_view(b, candidate=True)
            self.assertGreater(_iou(actual['mask'], expected['mask']), .97,
                               'gray reference canvas was scored as the person')


if __name__ == '__main__':
    unittest.main()
