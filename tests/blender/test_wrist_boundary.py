import sys,unittest
from pathlib import Path
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import review_ch101_wrist_boundary as review

class BoundaryTests(unittest.TestCase):
    def test_sides_are_disjoint_and_exclude_remote_body(self):
        points=[Vector(p) for p in [(0,0,.01),(.01,0,.01),(0,.01,.01),(0,0,-.01),(.01,0,-.01),(0,.01,-.01),(.5,0,0)]]
        faces=[(0,1,2),(3,4,5),(0,3,1),(0,6,1)]
        result=review.classify(points,faces,(0,0,0),(0,0,1))
        self.assertEqual(result['PROXIMAL_GEOMETRIC'],[0]);self.assertEqual(result['DISTAL_GEOMETRIC'],[1])
        self.assertEqual(result['PLANE_STRADDLING'],[2]);self.assertEqual(result['OUTSIDE_REVIEW_ROI'],[3])
        self.assertEqual(sorted(i for values in result.values() for i in values),list(range(4)))
    def test_axis_reversal_swaps_sides(self):
        p=[Vector(v) for v in [(0,0,.01),(.01,0,.01),(0,.01,.01)]]
        self.assertEqual(review.classify(p,[(0,1,2)],(0,0,0),(0,0,-1))['DISTAL_GEOMETRIC'],[0])
    def test_zero_axis_rejected(self):
        with self.assertRaises(ValueError):review.classify([],[],(0,0,0),(0,0,0))

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(BoundaryTests))
    if not result.wasSuccessful():raise RuntimeError('BOUNDARY_TEST_FAILED')
