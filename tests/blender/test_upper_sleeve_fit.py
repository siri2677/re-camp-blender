import math
from pathlib import Path
import sys
import unittest
import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/blender'))
import fit_ch101_upper_sleeve as upper


class UpperSleeveTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)

    def fixture(self):
        cloth = upper.join.sleeve.build(Vector(), (0,0,1), (1,0,0))
        cuff = upper.join.sleeve.build(Vector(), (0,0,1), (1,0,0), ((-.015,.022,.031),(0,.022,.031)))
        joined, _ = upper.join.join_parts(cuff,cloth,Vector(),(0,0,1),(1,0,0))
        sections = {}
        for z in (.047,.065,.074,.083,.098):
            center = Vector((.004,0,z))
            points = [list(center+Vector((.034*math.cos(2*math.pi*j/64),.038*math.sin(2*math.pi*j/64),0))) for j in range(64)]
            sections[z] = dict(points=points,centroid=list(center),closed=True)
        return cloth, joined, sections

    def test_fit_locks_lower_vertices_uv_and_originals(self):
        cloth, joined, sections = self.fixture()
        before = upper.c.guide.digest([cloth,joined])
        obj, report = upper.fitted_copy(joined,cloth,Vector(),(0,0,1),(1,0,0),sections)
        self.assertEqual(report['changedVertices'],256)
        self.assertLess(report['maxDisplacementMeters'],upper.MAX_DISPLACEMENT)
        for a,b in zip(obj.data.vertices,joined.data.vertices):
            if b.co.z <= upper.LOCKED_HEIGHT+1e-6:
                self.assertLess((a.co-b.co).length,1e-7)
        self.assertLess(report['maxPairedWallDistanceChangeMeters'],1e-7)
        self.assertEqual(upper.c.wrist.self_surface_pairs(obj),0)
        self.assertEqual(upper.c.author.shape_audit(obj)['nonManifoldEdges'],0)
        self.assertEqual([tuple(p.uv) for p in obj.data.uv_layers.active.data],
                         [tuple(p.uv) for p in joined.data.uv_layers.active.data])
        self.assertEqual(before,upper.c.guide.digest([cloth,joined]))
        self.assertFalse(obj['sourceReplacementAllowed'])
        self.assertFalse(obj['unityInputAllowed'])

    def test_excessive_fit_and_wrong_plane_rejected(self):
        cloth, joined, sections = self.fixture()
        sections[.098]['centroid'][2] += .01
        with self.assertRaisesRegex(ValueError,'HEIGHT_MISMATCH'):
            upper.fitted_copy(joined,cloth,Vector(),(0,0,1),(1,0,0),sections)
        sections[.098]['centroid'][2] -= .01
        sections[.098]['centroid'][0] += .1
        for p in sections[.098]['points']:
            p[0] += .1
        with self.assertRaisesRegex(ValueError,'25MM_BOUND'):
            upper.fitted_copy(joined,cloth,Vector(),(0,0,1),(1,0,0),sections)

    def test_edge_identity_preserves_submicrometre_section_segments(self):
        # Two distinct source edges have section points <1 micrometre apart.
        angles = [0, .00001]+[2*math.pi*j/16 for j in range(1,16)]
        n = len(angles)
        points = [(math.cos(a)*.04,math.sin(a)*.04,z) for z in (-.1,.1) for a in angles]
        faces = [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
        faces.extend((tuple(reversed(range(n))),tuple(range(n,2*n))))
        mesh = bpy.data.meshes.new('NearEdges');mesh.from_pydata(points,[],faces);mesh.update()
        obj = bpy.data.objects.new('NearEdges',mesh);bpy.context.scene.collection.objects.link(obj)
        loop = upper.source_section(obj,Vector(),(0,0,1))
        self.assertTrue(loop['closed'])
        self.assertEqual(loop['pointCount'],n*2)
        self.assertGreater(loop['areaSquareMeters'],.004)
        with self.assertRaisesRegex(ValueError,'PLANE_VERTEX_AMBIGUOUS'):
            upper.source_section(obj,Vector((0,0,.1)),(0,0,1))

    def test_region_partitions_all_faces_and_excludes_remote_geometry(self):
        bpy.ops.mesh.primitive_cylinder_add(vertices=16,radius=.03,depth=.4)
        obj = bpy.context.object
        points, faces = upper.c.fit.geometry(obj)
        n, count = len(points), len(faces)
        points += [p+Vector((1,0,0)) for p in points]
        faces += [tuple(i+n for i in face) for face in faces]
        report = upper.region_review(points,faces,Vector(),(0,0,1))
        assigned = [i for ids in report['triangleClasses'].values() for i in ids]
        self.assertEqual(sorted(assigned),list(range(len(faces))))
        self.assertTrue(all(i<count for i in report['selectedConnectedTriangleIndices']))
        self.assertFalse(report['cutAllowed'])
        self.assertFalse(report['anatomicalBoundaryVerified'])
        with self.assertRaisesRegex(ValueError,'INVALID_REGION'):
            upper.region_review(points,faces,Vector(),(0,0,0))


if __name__ == '__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(UpperSleeveTests))
    if not r.wasSuccessful():
        raise RuntimeError('UPPER_SLEEVE_TEST_FAILED')
