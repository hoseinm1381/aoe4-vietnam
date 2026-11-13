"""Rebuild the Lam Son field uniform on its original three native rig tiers."""
from pathlib import Path
import importlib
import json
import shutil
import sys

import bpy
from mathutils import Vector
import numpy as np

project, stage, python_packages = map(Path, sys.argv[sys.argv.index('--')+1:])
sys.path[:0] = [str(Path(__file__).resolve().parent), str(python_packages)]
from mesh import Builder, charts

def join(objects, name):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.hide_set(False)
        obj.hide_viewport = False
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    result = bpy.context.object
    result.name = name
    tri = result.modifiers.new('Explicit triangles', 'TRIANGULATE')
    bpy.ops.object.modifier_apply(modifier=tri.name)
    return result

def weights(obj, palette):
    """Fold unavailable bones up to the closest legal ancestor."""
    rig = next(m.object for m in obj.modifiers if m.type=='ARMATURE')
    bones = rig.data.bones
    groups = [g.name for g in obj.vertex_groups]
    rows = []
    for vertex in obj.data.vertices:
        row = {}
        for source in vertex.groups:
            name = groups[source.group]
            while name not in palette:
                parent = bones[name].parent
                assert parent
                name = parent.name
            row[name] = row.get(name,0)+source.weight
        best = sorted(row.items(), key=lambda x: -x[1])[:4]
        assert best and sum(w for _,w in best)>0
        rows.append(best)
    obj.vertex_groups.clear()
    for vertex, row in enumerate(rows):
        total = sum(w for _,w in row)
        for name, weight in row:
            group = obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
            group.add([vertex],weight/total,'REPLACE')

def paint(original, target, age):
    from PIL import Image
    src = np.asarray(Image.open(original/'albedo.png').convert('RGBA')).copy()
    mask = np.asarray(Image.open(original/'pattern.png').convert('RGBA')).copy()
    normal = np.asarray(Image.open(original/'normal.png').convert('RGBA')).copy()
    width = src.shape[1]
    palette = {'tunic':(89,79,55),'sleeve_l':(107,97,70),'sleeve_r':(107,97,70),
               'headcloth':(125,125,125),'armour':(98,98,98),
               'linen':(144,137,112),'leather':(76,54,36)}
    for name, color in palette.items():
        x,y,w,h = charts()[name]
        x0,y0,nx,ny = (round(n*width) for n in (x,y,w,h))
        cut = np.s_[width-y0-ny:width-y0, x0:x0+nx]
        sample = src[cut][:,:,:3].astype(float)
        gray = sample.mean(2)
        shade = (gray-np.median(gray))*.72
        if name=='armour':
            yy,xx = np.mgrid[:ny,:nx]
            xx,yy = xx/nx,yy/ny
            seam = np.exp(-((np.sin((xx*9+yy*3)*np.pi)/.12)**2))
            seam += np.exp(-((np.sin((xx*9-yy*3)*np.pi)/.12)**2))
            shade = -23*seam+6*np.sin(xx*np.pi*18)*np.sin(yy*np.pi*6)
            dy,dx = np.gradient(shade)
            normal[cut][:,:,:2] = np.clip(128-np.stack((dx,dy),axis=2)*5,70,185)
        src[cut][:,:,:3] = np.clip(np.asarray(color)[None,None,:]+shade[:,:,None],20,218)
        if name in ('headcloth','armour'):
            mask[cut][:,:,0] = 255
        elif name == 'tunic':
            mask[cut][:,:,0] = 0
            band = mask[cut][:,:,0]
            band[-ny//7:] = 255
        elif name.startswith('sleeve'):
            mask[cut][:,:,0] = 0
            band = mask[cut][:,:,0]
            band[:ny//4] = 255
    for label,image in [('albedo',src),('pattern',mask),('normal',normal)]:
        Image.fromarray(image).save(target/f'{label}.png')
    for label in ('roughness','metalness'):
        image = Image.open(original/f'{label}.png').convert('RGBA')
        x,y,w,h = charts()['armour']
        x0,y0,nx,ny = (round(n*width) for n in (x,y,w,h))
        value = 217 if label=='roughness' else 0
        image.paste((value,value,value,255),(x0,width-y0-ny,x0+nx,width-y0))
        image.save(target/f'{label}.png')

def run(age):
    family=f'skirmisher{age}'
    original=project/f'authoring/art/exports/release_083/{family}/r12'
    model=project/f'authoring/art/authoring/release_083/{family}/r12/model.blend'
    output=stage/family
    output.mkdir()
    bpy.ops.wm.open_mainfile(filepath=str(model),load_ui=False)
    rig,=[o for o in bpy.data.objects if o.type=='ARMATURE']
    rig.animation_data_clear()
    rig.data.pose_position='REST'
    before={b.name:[list(row) for row in b.matrix_local] for b in rig.data.bones}
    prior = [bpy.data.objects[f'body_lod{i}'] for i in range(1,4)]
    palettes = [{g.name for g in ob.vertex_groups if any(
        entry.group==g.index and entry.weight>0 for v in ob.data.vertices for entry in v.groups)}
        for ob in prior]
    for ob in prior:
        bpy.data.objects.remove(ob,do_unlink=True)
    for i in (2,3):
        bpy.data.materials[f'lod{i}'].name=f'Original tier {i}'
    keep = ('Reworked official Chinese head and hands','Collar seated inner neck',
            'Gathered trousers','Cloth gaiter','Soft leather shoe','Spare bamboo',
            'Spare forged','Leather javelin carrier')
    parts = [o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith(keep)]
    assert len(parts)>=10, [o.name for o in parts]
    material = parts[0].data.materials[0]
    native = Builder(rig,material)
    uv = charts()
    pelvis='metarig_pelvis'
    chest='metarig_ribcage'
    head='metarig_head'
    cloth = [(.84,.24,.145),(.88,.245,.151),(.97,.224,.142),(1.03,.19,.123),
             (1.13,.201,.137),(1.26,.224,.151),(1.40,.225,.143),(1.49,.192,.111),(1.57,.080,.073)]
    native.loft('Short cross-collar field tunic',[((0,0,z),a,b) for z,a,b in cloth],
        [{pelvis:1} if z<1.08 else {chest:1} for z,_,_ in cloth], uv['tunic'], sides=36,fold=.045,caps=False)
    for side in ('l','r'):
        prefix='metarig_'+side
        shoulder, elbow, wrist = [native.bone(prefix+k) for k in ('armupper1','armlower1','armlower2')]
        first, last = prefix+'armupper1',prefix+'armlower1'
        native.loft('Bound short sleeve '+side,
                    [(shoulder,.082,.093),(shoulder.lerp(elbow,.48),.095,.089),
                     (shoulder.lerp(elbow,.84),.078,.075),(elbow.lerp(wrist,.23),.068,.063)],
                    [{first:1},{first:1},{first:.45,last:.55},{last:1}],
                    uv['sleeve_'+side],sides=24,fold=.06,axis='path',caps=False)
        palm=native.bone(prefix+'armpalm')
        native.loft('Linen forearm wrap '+side,[(elbow.lerp(wrist,.20),.069,.064),
                    (wrist,.054,.050),(palm.lerp(wrist,.12),.039,.034)],last,
                    uv['linen'],sides=20,fold=.03,axis='path',caps=False)
    quilt = [(1.10,.209,.143),(1.18,.223,.154),(1.29,.239,.164),
             (1.40,.243,.152),(1.49,.195,.124)]
    for index,(z,a,b) in enumerate(quilt):
        quilt[index] = (z,a+.004*(age-2),b+.003*(age-2))
    native.loft('Quilted sleeveless fighting vest',[((0,0,z),a,b) for z,a,b in quilt],chest,
                uv['armour'],sides=40,fold=.023,caps=False)
    native.ribbon('Linen collar binding',[(.070,-.058,1.575),(.108,-.115,1.49),
                 (.055,-.158,1.39),(-.038,-.164,1.28),(-.127,-.153,1.19)],
                 [.033,.038,.038,.031,.025],chest,uv['linen'])
    native.loft('Wrapped waist tie',[((0,0,z),a,b) for z,a,b in
                [(1.031,.201,.139),(1.052,.203,.139),(1.086,.207,.144)]],pelvis,uv['leather'],sides=36)
    native.ribbon('Cloth waist knot',[(-.106,-.143,1.064),(-.14,-.154,1.015),
                 (-.16,-.16,.90)],[.06,.053,.033],pelvis,uv['headcloth'])
    native.loft('Folded tied headcloth',[((0,-.026,z),a,b) for z,a,b in
                [(1.84,.103,.106),(1.865,.115,.119),(1.895,.122,.129),
                 (1.923,.105,.111),(1.937,.055,.061)]],head,uv['headcloth'],sides=32,fold=.025)
    for offset in (0,.045):
        native.ribbon('Tied headcloth tail',[(.09+offset,.066,1.884),(.13+offset,.109,1.825),
                      (.117+offset,.128,1.71-offset)],[.045,.040,.026],head,uv['headcloth'],normal=(1,0,0))
    native.ribbon('Carrier strap',[(.134,-.124,1.49),(.087,-.171,1.38),
                 (-.019,-.172,1.245),(-.13,-.151,1.105)],[.026]*4,chest,uv['leather'])
    parts += native.parts
    copies = []
    for obj in parts:
        copy = obj.copy()
        copy.data=obj.data.copy()
        bpy.context.scene.collection.objects.link(copy)
        copies.append(copy)
    lods=[join(copies,'body_lod1')]
    for obj in parts:
        obj.hide_render=True
        obj.hide_set(True)
    for index,ratio in enumerate((.52,.27),2):
        obj=lods[0].copy()
        obj.data=lods[0].data.copy()
        obj.name=f'body_lod{index}'
        bpy.context.scene.collection.objects.link(obj)
        bpy.context.view_layer.objects.active=obj
        dec=obj.modifiers.new('Mesh detail','DECIMATE')
        dec.ratio=ratio
        bpy.ops.object.modifier_apply(modifier=dec.name)
        mat=material.copy()
        mat.name=f'lod{index}'
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        lods.append(obj)
    for index,obj in enumerate(lods):
        # All newly authored bones are also present on the original weighted skin.
        palette=palettes[index]|{'metarig_root'}
        weights(obj,palette)
        assert len(obj.data.uv_layers)==1 and len(obj.modifiers)==1
    assert before=={b.name:[list(row) for row in b.matrix_local] for b in rig.data.bones}
    paint(original,output,age)
    prefix = next(key for key in bpy.context.preferences.addons.keys() if key.endswith('.garrison'))
    exporter=importlib.import_module(prefix+'.unit_export')
    for mat in {o.data.materials[0] for o in lods}:
        for node in mat.node_tree.nodes:
            if node.type=='TEX_IMAGE' and node.name.startswith('083 '):
                role=node.name.removeprefix('083 ')
                node.image=bpy.data.images.load(str(output/f'{role}.png'),check_existing=True)
                if role!='albedo':node.image.colorspace_settings.name='Non-Color'
                node.image.pack()
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(output/'model.blend'))
    exporter.export_unit_model(rig,lods,output/'model.fbx',exporter.skeleton_records(rig),three_lods=False)
    shutil.copyfile(original/'model.rig',output/'model.rig')
    result={'bones':len(before),'triangles':[sum(len(f.vertices)-2 for f in o.data.polygons) for o in lods],
            'material_slots':[o.data.materials[0].name for o in lods]}
    assert result['material_slots']==['lod1','lod2','lod3'],result
    (output/'source-verification.json').write_text(json.dumps(result,indent=2))
    print(f'{family}: {result}',flush=True)

for age in (2,3,4):
    run(age)

