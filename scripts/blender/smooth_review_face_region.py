"""Bounded curvature smoothing of an estimated face region; no landmark claims."""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Vector

STRATEGY='CH101_ESTIMATED_FACE_CURVATURE_CORRECTION_V001'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def smooth(objects):
    points=[o.matrix_world@v.co for o in objects for v in o.data.vertices]
    low=min(p.z for p in points)
    height=max(p.z for p in points)-low
    ymin,ymax=min(p.y for p in points),max(p.y for p in points)
    front_mid=(ymin+ymax)/2
    stats=[]
    for obj in objects:
        if obj.data.users>1:
            obj.data=obj.data.copy()
        original=[obj.matrix_world@v.co for v in obj.data.vertices]
        adjacency=[set() for _ in original]
        for e in obj.data.edges:
            a,b=e.vertices
            adjacency[a].add(b)
            adjacency[b].add(a)
        weights=[]
        for p in original:
            z=(p.z-low)/height
            vertical=math.sin(math.pi*(z-.80)/.10)**2 if .80<z<.90 else 0
            frontal=max(0,min(1,(front_mid-p.y)/max((ymax-ymin)*.25,1e-6)))
            weights.append(vertical*frontal)
        current=[p.copy() for p in original]
        for _ in range(4):
            for factor in (.25,-.26):
                previous=[p.copy() for p in current]
                for i, neighbors in enumerate(adjacency):
                    if not weights[i] or not neighbors:
                        continue
                    average=sum((previous[j] for j in neighbors),Vector())/len(neighbors)
                    proposed=previous[i]+factor*weights[i]*(average-previous[i])
                    displacement=proposed-original[i]
                    # Maximum displacement is 0.5% of height (8.4 mm at 1.68 m).
                    if displacement.length>height*.005:
                        proposed=original[i]+displacement.normalized()*height*.005
                    current[i]=proposed
        inverse=obj.matrix_world.inverted()
        moved=[]
        for v,p,before,w in zip(obj.data.vertices,current,original,weights):
            if w>0:
                v.co=inverse@p
            moved.append((p-before).length)
        obj.data.update()
        stats.append({'object':obj.name,'vertexCount':len(original),
            'affectedVertexCount':sum(m>1e-8 for m in moved),
            'maxDisplacement':max(moved,default=0),
            'outsideRegionUnchanged':all(m==0 for m,w in zip(moved,weights) if not w)})
    return stats


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--input-blend',required=True,type=Path)
    p.add_argument('--input-sha256',required=True)
    p.add_argument('--output-blend',required=True,type=Path)
    p.add_argument('--report',required=True,type=Path)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    if sha(args.input_blend)!=args.input_sha256:
        raise ValueError('INPUT_SHA256_MISMATCH')
    if args.output_blend.exists() or args.output_blend.resolve()==args.input_blend.resolve():
        raise ValueError('OUTPUT_ALREADY_EXISTS')
    bpy.ops.wm.open_mainfile(filepath=str(args.input_blend.resolve()))
    objects=[o for o in bpy.context.scene.objects if o.type=='MESH' and len(o.data.vertices) and not o.name.startswith('ReviewFloor_')]
    if not objects:
        raise ValueError('NO_MESH')
    stats=smooth(objects)
    for key,value in {'source_status':'AI_GENERATED_CANDIDATE_NOT_PRODUCTION','gate_b':'PENDING_HUMAN_REVIEW',
                      'unity_input_allowed':False,'production_promotion_allowed':False}.items():
        bpy.context.scene[key]=value
    args.output_blend.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output_blend.resolve()))
    report={'candidateId':STRATEGY,'strategyId':STRATEGY,'status':'ESTIMATED_FACE_PATCH_SMOOTHED_NOT_APPROVED',
            'sourceStatus':'AI_GENERATED_CANDIDATE_NOT_PRODUCTION','gateB':'PENDING_HUMAN_REVIEW',
            'unityInputAllowed':False,'productionPromotionAllowed':False,
            'inputBlendSha256':args.input_sha256,'outputBlendSha256':sha(args.output_blend),
            'region':'ESTIMATED_FRONT_FACE_Z_0.80_TO_0.90_NOT_SEMANTIC_LANDMARKS',
            'iterations':4,'lambda':.25,'mu':-.26,'maximumDisplacementHeightRatio':.005,'objects':stats,
            'semanticGeometryCreated':False}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
