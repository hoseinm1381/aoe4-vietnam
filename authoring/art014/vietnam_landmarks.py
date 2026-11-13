"""Paint Vietnamese landmark atlases with distinct architectural finishes."""
from pathlib import Path
from collections import defaultdict
import json, sys, struct
import numpy as np
from PIL import Image
from lifecycle_repair import stage,repos,readback,put,stock_game
from mesh_surface import mesh,s,rc,mv
from persian_keep import decode,encode_srgb_bc1,encode_bc3,levels

# Atlas order is upper row left to right, then lower row left to right.
# The mask selects compact decorative atlas regions, measured on model surfaces.
PLANS={
 'one_pillar':([(178,88,56),(132,62,48),(171,102,57),(164,165,131),(180,172,143),(46,109,105),(75,118,66),(142,102,60)],(1,5,7)),
 'pho_minh':([(167,79,57),(102,58,41),(144,69,48),(133,140,121),(172,158,123),(43,88,101),(82,108,61),(145,96,59)],(1,5,7)),
 'citadel':([(143,104,76),(94,57,49),(53,87,107),(158,149,131),(145,117,82),(69,56,53),(210,192,146),(145,97,59)],(1,2,7)),
 'foundry':([(56,51,47),(182,100,48),(86,109,119),(76,112,56),(161,136,110),(104,58,32),(203,161,104),(142,62,36)],(2,4,7)),
 'garden':([(44,119,88),(155,109,74),(45,106,124),(82,133,68),(164,164,112),(116,68,48),(199,182,122),(151,78,49)],(2,5,7)),
 'university':([(60,78,110),(153,65,67),(120,113,151),(74,120,86),(166,145,136),(121,78,72),(205,184,151),(129,58,72)],(1,2,7)),
 'wonder':([(53,108,124),(183,107,65),(196,152,62),(93,125,57),(156,132,103),(135,69,49),(222,191,134),(179,82,50)],(2,5,7)),
 'ministry':([(146,105,58),(145,94,54),(167,76,55),(180,146,83),(145,106,73),(51,108,111),(93,123,55),(164,112,54)],(1,2,7)),
}
def source_name(value):
    return value.replace(chr(92),'/').lower()
def paint(key, original, mask):
    values=np.asarray(original).copy()
    h,w=values.shape[:2]
    for i,color in enumerate(PLANS[key][0]):
        u,v=i%4,i//4
        if key=='ministry':
            # The right half is baked stock furniture and elephants.
            width=w//8
        else:width=w//4
        ys,xs=slice(v*h//2,(v+1)*h//2),slice(u*width,(u+1)*width)
        rgb=values[ys,xs,:3]
        light=rgb @ np.array([.2126,.7152,.0722])
        rel=light-np.median(light)
        tex=np.array(color)+rel[:,:,None]*.82
        rgb[:]=np.clip(tex,10,239).astype(np.uint8)
        selected=mask[ys,xs,2]>127
        rgb[selected]=np.clip(134+rel[selected,None]*.75,80,191).astype(np.uint8)
    return values
def compute_samples(geo,h,w):
    buckets=np.zeros((h,w))
    for _,_,xyz,uv,ids in mesh(geo):
        p=xyz[ids]
        area=np.linalg.norm(np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]),axis=1)*.5
        t=np.array([[1/3,1/3,1/3],[.6,.2,.2],[.2,.6,.2],[.2,.2,.6]])
        sample=np.einsum('sa,fad->fsd',t,uv[ids]).reshape(-1,2)%1
        x=(sample[:,0]*w).astype(int)
        y=h-1-(sample[:,1]*h).astype(int)
        np.add.at(buckets,(y,x),np.repeat(area/4,4))
    return buckets
def mask_atlas(key,shape,weights):
    h,w=shape[:2]
    yy,xx=np.indices((h,w))
    tw=w//8 if key=='ministry' else w//4
    index=(xx//tw)+4*(yy//(h//2))
    allowed=np.isin(index,PLANS[key][1])
    if key=='ministry':allowed &= xx<w//2
    # Prefer broad bands inside selected cloth, eave and trim tiles.
    distance=abs((yy%(h//2))/(h//2)-.5)
    order=np.argsort(np.where(allowed,distance,2).ravel(),kind='stable')
    cumulative=np.cumsum(weights.ravel()[order])
    cut=min(np.searchsorted(cumulative,weights.sum()*.13),len(order)-1)
    limit=distance.ravel()[order[cut]]
    chosen=allowed & (distance<=limit)
    covered=float(weights[chosen].sum()/weights.sum())
    if covered<.055:
        # Fallback to narrow bands across other painted architectural tiles.
        order=np.argsort(np.where((xx<w//2) if key=='ministry' else np.ones_like(allowed),distance,2).ravel(),kind='stable')
        cutoff=min(np.searchsorted(np.cumsum(weights.ravel()[order]),weights.sum()*.12),len(order)-1)
        chosen=(distance<=distance.ravel()[order[cutoff]])
        if key=='ministry': chosen &= xx<w//2
        covered=float(weights[chosen].sum()/weights.sum())
    assert .05<=covered<=.25,(key,covered)
    rgba=np.zeros(shape,dtype=np.uint8)
    rgba[:,:,2][chosen]=255
    rgba[:,:,3]=255
    return rgba,covered

OLD=rc.lp_string('object_collection')
NEW=rc.lp_string('structure_collection')


def geometry(raw):
    doc=rc.parse(raw)
    def replace(c):
        if c.tag!=b'GEOM':
            return None
        header=next(x for x in c.children if x.tag==b'GOHD')
        assert OLD+rc.lp_string('ObjectCollectionDataStream') in header.payload
        vh,vb,ih,ib=[x for x in c.children if x.tag in (b'GEOB',b'GEOC')]
        assert len(vh.payload)==2116
        meta=bytearray(vh.payload)
        # Exact stream declaration fields verified against all four real cooks.
        for pos,src,dst in ((972,16,20),(1552,30,13),(1556,0,4),(1560,0,16)):
            assert meta[pos:pos+4]==struct.pack('<I',src),(pos,meta[pos:pos+4])
            meta[pos:pos+4]=struct.pack('<I',dst)
        n,zero,stride,unknown=struct.unpack_from('<4I',vb.payload)
        assert stride==20 and len(vb.payload)==16+n*20
        v=np.frombuffer(vb.payload,np.uint8,offset=16).reshape(-1,20)
        buf=np.concatenate([v[:,:16],v[:,12:16],v[:,16:]],axis=1).tobytes()
        replacements={
            header.offset:header.payload.replace(OLD+rc.lp_string('ObjectCollectionDataStream'),
                    NEW+rc.lp_string('StructureCollectionPositionDataStream')),
            vh.offset:bytes(meta),vb.offset:struct.pack('<4I',n,zero,24,unknown)+buf,
        }
        return b''.join(rc.pack_chunk(x.kind,x.tag,replacements.get(x.offset,x.payload),
                    version=x.version,name=x.name) for x in c.children)
    return rc.rebuild(doc,replace)


def replace_effect(raw):
    doc=rc.parse(raw)
    [data]=[c.children[0] for c in rc.walk(doc.roots) if c.tag==b'MSCL']
    assert data.payload.count(OLD)==1
    return rc.rebuild(doc,lambda c:data.payload.replace(OLD,NEW) if c.offset==data.offset else None)


def recolor():
    base=readback('vietnam')
    out=stage/'vietnam'
    masters=out/'masters';masters.mkdir(exist_ok=True)
    g=stock_game.current()
    # Use the full shader block that ships on a rendered structure.
    stock=readback('berbers')
    example=next(stock.glob('art/**/tlemcen_age03/tlemcen_age03.rrmaterial'))
    donor=rc.parse(example.read_bytes()).roots[:2]
    assert [x.decoded_name for x in donor]==['main','main_collection']
    source_mask=next(stock.glob('art/scenario/berbers_owner_013/structure_*.rrtex'))
    albedo_template=(repos/'aoe4-korea/inputs/native/art/kr036/architecture/gyeongbok_palace.rrtex').read_bytes()
    inventory=defaultdict(list)
    for material in (base/'art/scenario').rglob('*.rrmaterial'):
        if not any(x in material.as_posix() for x in ('ministry','cc070','citadel','one_pillar','pho_minh')):continue
        raw=material.read_bytes()
        slots=[mv.material_slots(s(c))['textures'] for c in rc.parse(raw).roots if c.tag==b'GMat']
        if len(slots)!=2 or not all('albedoTexture' in t for t in slots):continue
        texture=source_name(slots[0]['albedoTexture'])
        key=Path(texture).parent.name
        if key in PLANS: inventory[key].append((material,texture,slots))
    assert set(inventory)==set(PLANS),inventory.keys()
    # Stock fully opaque layered shading requires no alpha cutouts on these
    # architectural atlases. Preserve the geometry/state partition and UV0.
    sys.path.insert(0,str(repos/'aoe4-berbers/tools'))

    record={}
    for key,rows in sorted(inventory.items()):
        names={t for _,t,_ in rows}; assert len(names)==1
        texture=next(iter(names))
        original=decode(base/texture,out/(key+'.dds'))
        h,w=original.shape[:2]
        weights=sum(compute_samples(material.with_suffix('.rrgeom').read_bytes(),h,w) for material,_,_ in rows)
        mask,coverage=mask_atlas(key,original.shape,weights)
        painted=paint(key,original,mask)
        maskname=f'art/scenario/vn014/landmarks/{key}-owner.rrtex'
        albedo=f'art/scenario/vn014/landmarks/{key}-albedo.rrtex'
        color=Image.fromarray(painted)
        owner=Image.fromarray(mask)
        color.save(masters/(key+'-albedo.png'))
        owner.save(masters/(key+'-owner.png'))
        put('vietnam',albedo,encode_srgb_bc1(albedo_template,albedo,color))
        put('vietnam',maskname,encode_bc3(source_mask.read_bytes(),maskname.removesuffix('.rrtex'),list(levels(owner))))
        for material,_,slots in rows:
            stem=material.with_suffix('')
            rgm=stem.with_suffix('.rgm').read_bytes()
            geo=stem.with_suffix('.rrgeom').read_bytes()
            prepared=geometry(geo)
            changed=replace_effect(rgm)
            rel=stem.relative_to(base).as_posix()
            for ext,data in (('.rgm',changed),('.rrgeom',prepared)):put('vietnam',rel+ext,data)
            patches=[]
            for before,block,inputs in zip(rc.parse(material.read_bytes()).roots,donor,slots,strict=True):
                spec=mv.material_slots(s(block))['textures']
                maps={}
                for field in spec:
                    if field in ('albedoTex','albedoTex2','albedoTex3','albedoTex4','albedoTex5','albedoTex6'):
                        maps[field]=albedo
                    elif field=='maskTex5':maps[field]=maskname
                    elif field in ('normalMap','normalMap2','normalMap3','normalMap4'):
                        maps[field]=inputs['normalMap']
                    elif field in ('metalTex','metalTex2','metalTex3','metalTex4'):
                        maps[field]=inputs['metalTex']
                    elif field in ('maskTex2','maskAlpha','overlay1Mask','overlay2Mask','terrainBlendMask'):
                        maps[field]='art/scenario/vn014/landmarks/black.rrtex'
                data=mv.rewrite_material(s(block),{k:v.replace('/',chr(92)) for k,v in maps.items()},{})
                result,=rc.parse(data).roots
                patches.append(rc.pack_chunk(result.kind,result.tag,result.payload,version=result.version,name=before.name))
            put('vietnam',rel+'.rrmaterial',rc.pack_document(patches))
        record[key]={'models':len(rows),'area_covered':coverage}
        print(key,len(rows),round(coverage*100,2),flush=True)
    black=next(stock.glob('art/**/berber_tent_age1/black.rrtex'))
    raw=black.read_bytes()
    name='art/scenario/vn014/landmarks/black.rrtex'
    put('vietnam',name,rc.rebuild(rc.parse(raw),lambda c:rc.Rename(name.removesuffix('.rrtex').replace('/',chr(92)).encode()+bytes(1)) if c.tag==b'TXTR' else None))
    (masters/'landmark-coverage.json').write_text(json.dumps(record,indent=2))
if __name__=='__main__':recolor()

