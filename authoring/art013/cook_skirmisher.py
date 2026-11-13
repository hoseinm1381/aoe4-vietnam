"""Create a minimal native cook project for the three skirmisher bodies."""
import json
from pathlib import Path
import re
import shutil
import sys
import xml.etree.ElementTree as ET

repo, stage, template = map(Path,sys.argv[1:])
project = stage/'sk2'
shutil.copytree(template, project, ignore=shutil.ignore_patterns('art','evidence','cache','archives'))
source = project/'source'
burn = source/'_default.burnproj'
text = burn.read_text(encoding='utf-8-sig')
rules = (repo/'authoring/art/recipes/release_079/art-burn-rules.xml').read_text(encoding='utf-8')
models = re.findall(r'<BurnRule>.*?</BurnRule>',rules,re.S)
tex_rule = ('<BurnRule><Alias>data</Alias><Burner>RRTextureBurner</Burner>'
            '<Configurations>Debug Release Profile RTM</Configurations><Excludes></Excludes>'
            '<Includes>__TEXTURE_SCOPE__</Includes><IsEnabled>true</IsEnabled>'
            '<NamedParameters>Static Textures</NamedParameters><PathOverride i:nil="true"/>'
            '<Target>Archive</Target></BurnRule>')
tex_scope = re.search(r'<Includes>(.*?)</Includes>',tex_rule,re.S).group(1)
pattern_label = 'Vietnam RGB Owner Masks'
params, = [part for part in re.findall(r'<NamedParameters>.*?</NamedParameters>',text,re.S)
            if '<Name>Static Textures</Name>' in part]
native = params.replace('<Name>Static Textures</Name>', f'<Name>{pattern_label}</Name>')
for key,value in {'ColourSpace':'Linear','PreferredFormat':'BC3','ForceFormat':'true',
                  'FlipImage':'true','ShrinkSingleColorTextures':'false',
                  'PremultiplyAlpha':'false'}.items():
    native,count = re.subn(rf'(<d4p1:{key}>).*?(</d4p1:{key}>)',
                          lambda m:m[1]+value+m[2],native)
    assert count==1,(key,count)
text=text.replace('</NamedBurnerParameters>',native+'</NamedBurnerParameters>')
for age in (2,3,4):
    rel = f'art/scenario/garrison/cc076/skirmisher{age}'
    body = source/rel
    body.mkdir(parents=True)
    for name in ('albedo.png','normal.png','roughness.png','metalness.png','pattern.png','model.fbx','model.rig'):
        shutil.copyfile(stage/f'unit3/skirmisher{age}'/name,body/name)
    marker = template/'source/art/scenario/chagatai/ordu_healthy/ordu_healthy.rgo'
    shutil.copyfile(marker,body/'model.rgo')
    (body/'model.rgotemplate').write_text('<ObjectTemplate><LodDistances/></ObjectTemplate>\n')
    doc=ET.Element('materialSet')
    for lod in (1,2,3):
        mat=ET.SubElement(doc,'material',name=f'lod{lod}',type='shader',source='unit')
        for slot,name in {'albedoTexture':'albedo','normalMap':'normal','metalTex':'metalness',
                         'roughnessTex':'roughness','patternTex':'pattern'}.items():
            ET.SubElement(mat,'param',name=slot,type='tex2D',value=f'{rel}/{name}.png')
    ET.indent(doc)
    (body/'model.material').write_bytes(ET.tostring(doc,encoding='utf-8',xml_declaration=True))
    scope=rel.replace('/','\\')
    additions=[r.replace('__MODEL_PATH__',scope) for r in models]
    images=';'.join(scope+'\\'+name+'.png' for name in ('albedo','normal','metalness','roughness'))
    additions.append(tex_rule.replace(tex_scope,images))
    additions.append(tex_rule.replace(tex_scope,scope+'\\pattern.png').replace(
                     '<NamedParameters>Static Textures</NamedParameters>',
                     f'<NamedParameters>{pattern_label}</NamedParameters>'))
    text=text.replace('</Rules>','\n'.join(additions)+'\n</Rules>',1)
burn.write_text(text,encoding='utf-8')
ET.parse(burn)
print(project/'garrison_static.aoe4mod',flush=True)

