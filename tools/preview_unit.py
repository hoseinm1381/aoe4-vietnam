"""Render the rebuilt Skirmisher at the game angle in two player colors."""
from pathlib import Path
import sys
import bpy
from mathutils import Vector

stage=Path(sys.argv[-1])
out=stage/'unit-preview'
out.mkdir(exist_ok=True)
for age in (2,3,4):
    bpy.ops.wm.open_mainfile(filepath=str(stage/f'unit3/skirmisher{age}/model.blend'),load_ui=False)
    scene=bpy.context.scene
    for obj in scene.objects:
        if obj.type=='MESH':
            obj.hide_render=obj.name!='body_lod1'
    scene.world=bpy.data.worlds.new('Soft daylight')
    scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.13,.16,.19,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.48
    target=Vector((0,0,.98))
    for name,pos,power,size in [('Key',(3,-4,5),450,3),('Fill',(-3,-3,2),210,2)]:
        light=bpy.data.objects.new(name,bpy.data.lights.new(name,'AREA'))
        scene.collection.objects.link(light)
        light.location=pos
        light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
        light.data.energy=power
        light.data.shape='DISK'
        light.data.size=size
    camera=bpy.data.objects.new('Game angle',bpy.data.cameras.new('Game angle'))
    scene.collection.objects.link(camera)
    scene.camera=camera
    camera.data.type='ORTHO'
    camera.data.ortho_scale=2.55
    camera.location=(3,-5,3.7)
    camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.engine='CYCLES'
    scene.cycles.samples=6
    scene.render.resolution_x=340
    scene.render.resolution_y=380
    scene.render.resolution_percentage=100
    mat=bpy.data.objects['body_lod1'].data.materials[0]
    for name,color in [('blue',(.055,.22,.90,1)),('red',(.90,.055,.035,1))]:
        mat.node_tree.nodes['OWNER PREVIEW'].outputs[0].default_value=color
        scene.render.filepath=str(out/f'age-{age}-{name}.png')
        bpy.ops.render.render(write_still=True)

