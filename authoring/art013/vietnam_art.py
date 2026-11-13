"""Apply Vietnamese architecture finishes and integrate the native Skirmisher cook."""
import json
from pathlib import Path
import shutil
import sys

import numpy as np
from PIL import Image
from garrison_shared import model_variants as mv, relic_chunky as rc, rrtex_decoder as rr

root, stage, color_tools = map(Path, sys.argv[1:])
sys.path.insert(0, str(color_tools))
from art037.srgb_landmarks import encode_srgb_bc1

baseline=stage/'baseline'
overlay=stage/'overlay'
masters=stage/'building-masters'
masters.mkdir(exist_ok=True)
palettes={
 'ministry': (.18,(152,123,85)), 'pho_minh': (.25,(160,92,70)),
 'one_pillar': (.23,(122,144,112)), 'citadel': (.18,(158,119,84)),
 'foundry': (.19,(146,109,80)), 'garden': (.26,(99,143,124)),
 'university': (.24,(181,146,102)), 'wonder': (.22,(152,106,86)),
 'hq': (.24,(142,111,88)), 'keep_detail_age03': (.22,(123,131,130)),
 'monastery_detail_age03': (.24,(129,151,118)),
 'siege_workshop_detail_age03': (.22,(139,99,65)),
 'detail_archery_range_age02': (.19,(143,107,75)),
 'detail_blacksmith_age02': (.21,(111,113,111)),
 'detail_market_age02': (.22,(155,123,92)),
 'detail_stable_age02': (.20,(144,113,79)),
}
wood=('wood','roof','shingle')
def single_chunk(c):
    return rc.pack_document([rc.pack_chunk(c.kind,c.tag,c.payload,version=c.version,name=c.name)])

def path_of(value):
    return value.replace('\\','/').lower()

def put(path,data):
    output=overlay/path
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(data)

def finish(source, blend, target):
    rgb=np.asarray(source.convert('RGB'),dtype=float)
    luminosity=rgb @ np.array([.2126,.7152,.0722])
    pigment=np.asarray(target)[None,None,:]
    result=np.clip(rgb*(1-blend)+(pigment+((luminosity-115)*.74)[:,:,None])*blend,8,242)
    return Image.fromarray(np.rint(result).astype(np.uint8))

def structure_owner(path):
    raw=path.read_bytes()
    changes={}
    for c in rc.parse(raw).roots:
        if c.tag!=b'GMat':continue
        one=single_chunk(c)
        d=mv.material_slots(one)
        tx=d['textures']
        param=d['parameters']
        if 'maskTex5' not in tx or 'options' not in param:continue
        options=param['options']['values']
        bits=int(float(options[0]))
        if not any(bits&(1<<(layer-1)) and path_of(tx.get(f'albedoTex{layer}','')).split('/')[-1]
                   in {'6708399669590286008_packed.rrtex','4043818863494013394_packed.rrtex'}
                   for layer in (5,6,7)):
            continue
        # Preserve the stock mask and its geometry assignment. Increase the
        # response only on stock owner layers that are already active.
        key=next((k for k in ('mask45LevelMinMax','mask67LevelMinMax') if k in param),None)
        if key is None:continue
        result=mv.rewrite_material(one,{}, {key:['0','0.84','0','0.84']})
        c_new,=rc.parse(result).roots
        if c_new.payload!=c.payload:
            changes[c.offset]=c_new.payload
    if changes:put(path.relative_to(baseline).as_posix(),rc.rebuild(rc.parse(raw),lambda c:changes.get(c.offset)))
    return len(changes)

building_paths=('art/scenario/cc010/','art/scenario/cc020/','art/scenario/cc030/','art/scenario/cc040/',
 'art/scenario/cc050/','art/scenario/cc070/','art/scenario/cccastle/','art/scenario/garrison/community_040_details/')
materials=[p for p in sorted(baseline.rglob('*.rrmaterial'))
           if p.relative_to(baseline).as_posix().startswith(building_paths)]
used=set()
texture_paths=set()
dye_materials={}
for p in materials:
    rel=p.relative_to(baseline).as_posix()
    if any(key in rel for key in ('/t1/','/t2/','/tp/','paddy_edge')):continue
    for c in rc.parse(p.read_bytes()).roots:
        if c.tag!=b'GMat':continue
        for k,v in mv.material_slots(single_chunk(c))['textures'].items():
            texture=path_of(v)
            if not k.lower().startswith('albedo') or not (baseline/texture).is_file():
                continue
            if any(name in texture for name in palettes) or any(w in texture for w in ('vn_house_','_roof.rrtex')):
                texture_paths.add(texture)
    applied=structure_owner(p)
    if applied:dye_materials[rel]=applied

template = (color_tools.parent/'inputs/native/art/kr036/architecture/gyeongbok_palace.rrtex').read_bytes()
metrics={}
for index,member in enumerate(sorted(texture_paths)):
    source=baseline/member
    working=masters/f'{index:02d}.dds'
    stat=rr.decode_rrtex(source,working,validate_stream=True)
    if stat['internal_format']!=19:
        continue  # Non-sRGB source tiles may also carry a native data channel.
    image=Image.open(working).convert('RGB')
    color=next((palette for key,palette in palettes.items() if key in member),None)
    if color is None:
        if 'town_center' in member:color=(.22,(136,108,87))
        elif 'barracks' in member:color=(.18,(153,104,77))
        elif 'age01' in member:color=(.12,(140,117,83))
        elif 'age02' in member:color=(.16,(163,112,83))
        else:color=(.18,(128,137,119))
    result=finish(image,*color)
    png=masters/f'{index:02d}-{Path(member).parent.name}-{Path(member).stem}.png'
    result.save(png,optimize=True)
    put(member,encode_srgb_bc1(template,member,result))
    reread=rr.decode_rrtex(overlay/member,working,validate_stream=True)
    assert reread['internal_format']==19 and (reread['width'],reread['height'])==image.size
    metrics[member]={'source':png.name,'mips':reread['mip_count'],
        'decoded_rgba8_bytes':sum(4*max(1,image.width>>i)*max(1,image.height>>i)
                                 for i in range(reread['mip_count']))}

units={}
for age in (2,3,4):
    stem=f'art/scenario/garrison/cc076/skirmisher{age}/model'
    cooked=stage/'unit-cooked'
    prior=rc.parse((baseline/(stem+'.rgm')).read_bytes())
    fresh=rc.parse((cooked/(stem+'.rgm')).read_bytes())
    old={c.tag:c for c in prior.roots[0].children}
    new={c.tag:c for c in fresh.roots[0].children}
    assert all(new[k].payload==old[k].payload for k in (b'BANA',b'SKLN',b'MRKS',b'INFO',b'MRBP'))
    assert new[b'SKMS'].decoded_name == old[b'SKMS'].decoded_name == 'body'
    result=rc.rebuild(fresh,lambda c:old[b'MSBP'].payload if c.tag==b'MSBP' else None)
    put(stem+'.rgm',result)
    put(stem+'.rrgeom',(cooked/(stem+'.rrgeom')).read_bytes())
    mat=cooked/(stem+'.rrmaterial')
    put(stem+'.rrmaterial',mat.read_bytes())
    textures=set()
    for c in rc.parse(mat.read_bytes()).roots:
        slots=mv.material_slots(single_chunk(c))['textures']
        assert c.decoded_name in ('lod1','lod2','lod3')
        assert all(f'/skirmisher{age}/' in path_of(v) for k,v in slots.items() if k!='__default')
        textures.update(path_of(v) for k,v in slots.items() if k!='__default')
    for texture in sorted(textures):
        raw=(cooked/texture).read_bytes()
        put(texture,raw)
        if 'pattern' in next(c.decoded_name for c in rc.walk(rc.parse(raw).roots) if c.tag==b'TXTR'):
            dds=stage/f'skirmisher{age}-owner.dds'
            stat=rr.decode_rrtex(overlay/texture,dds,validate_stream=True)
            r=np.asarray(Image.open(dds).convert('RGB'))[:,:,0]
            assert 0.05 < (r>=128).mean() < .6
    units[age]={'original_skeleton_and_animator':True,'native_lods':3,'private_textures':sorted(textures)}
(stage/'vietnam-art-verification.json').write_text(json.dumps({
    'audited_building_materials':len(materials),'textures':metrics,'strengthened_owner_materials':dye_materials,
    'skirmisher':units},indent=2)+'\n',encoding='utf-8')
print(len(metrics),'building finish textures;',len(dye_materials),'owner-layer materials; three Skirmisher tiers',flush=True)

