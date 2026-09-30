"""Run through Blender MCP in the appended reference scene. Preserve the precision enclosure."""
import bpy, math
from mathutils import Vector
scene=bpy.context.scene
for o in list(scene.objects):
    if o.name.startswith(('optical-core__','optical-lenses__')):
        bpy.data.objects.remove(o,do_unlink=True)

def material(name,color,metal=.3,rough=.32):
    m=bpy.data.materials.new(name); m.use_nodes=True
    n=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    n.inputs['Base Color'].default_value=(*color,1);n.inputs['Metallic'].default_value=metal;n.inputs['Roughness'].default_value=rough
    return m
blue=material('Signal_Blue',(.08,.20,.29),.5)
gold=material('Signal_Copper',(.44,.24,.095),.65)
gray=material('Signal_Titanium',(.28,.34,.37),.6)
rail=material('Signal_Channels',(.50,.49,.46),.45)
substrate=material('Signal_Ceramic',(.77,.76,.71),.12)
created=[]
def mesh(name,verts,faces,mat):
    data=bpy.data.meshes.new(name);data.from_pydata(verts,[],faces);data.materials.append(mat)
    o=bpy.data.objects.new(name,data);scene.collection.objects.link(o);created.append(o);return o

def box(name,x,y,z,w,d,h,mat):
    verts=[(x+a*w/2,y+b*d/2,z+c*h/2) for a,b,c in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
    return mesh(name,verts,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],mat)

def trace(name,points,r,mat):
    verts=[];faces=[];sides=10
    for i,p in enumerate(points):
        for j in range(sides):
            a=2*math.pi*j/sides;verts.append((p[0],p[1]+r*math.cos(a),p[2]+r*math.sin(a)))
        if i:
            for j in range(sides):
                a=(i-1)*sides+j;b=(i-1)*sides+(j+1)%sides;c=i*sides+(j+1)%sides;d=i*sides+j;faces.append((a,b,c,d))
    o=mesh(name,verts,faces,mat)
    for p in o.data.polygons:p.use_smooth=True
    return o
for ch,mat in enumerate([blue,gold,gray]):
    center=2.53-ch*.66
    box('Signal channel substrate',0,-.027,center,3.48,.04,.48,substrate)
    for offset in [-.25,.25]:
        trace('Machined channel lip',[(-1.78,-.066,center+offset),(1.78,-.066,center+offset)],.008,rail)
    pts=[]
    for i in range(241):
        t=i/240
        v=.055*math.sin(t*24+ch)+.025*math.sin(t*62+ch)+(.21 if ch else .10)*math.exp(-((t-.61)/.037)**2)
        pts.append((-1.64+t*3.28,-.12,center+v))
    trace('Channel %d signal inlay'%ch,pts,.013,mat)
    for i in range(33):
        x=-1.64+i*.1025
        box('Calibrated time division',x,-.059,center-.17,.006,.008,.052 if i%4==0 else .026,rail)
    for x in [-1.85,1.85]:
        box('Channel terminal',x,-.09,center,.105,.075,.36,gray)
        for j in range(5):box('Gold contact',x,-.135,center-.12+j*.06,.069,.014,.021,gold)
for i in range(24):
    box('Sample memory contact',-.94+i*.084,-.073,.58,.035,.035,.11,gold)
# Join only the new inserts by material; keep every original enclosure component.
for mat in [blue,gold,gray,rail,substrate]:
    objs=[o for o in scene.objects if o.type=='MESH' and len(o.data.materials) and o.data.materials[0]==mat]
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:o.select_set(True)
    bpy.context.view_layer.objects.active=objs[0];bpy.ops.object.join();objs[0].name='signal-insert__'+mat.name
# Export uses Blender's default GLB format; no geometry decimation.
bpy.ops.object.select_all(action='SELECT')
bpy.ops.wm.save_as_mainfile(filepath=r'D:\Industrial_Time_Series_Agent\frontend\art\time-series-cassette.blend')
bpy.ops.export_scene.gltf(filepath=r'D:\Industrial_Time_Series_Agent\frontend\public\models\time-series-cassette.glb',use_selection=True,export_apply=True)
print('Saved precision cassette:',len(scene.objects),'objects',sum(len(o.data.vertices) for o in scene.objects if o.type=='MESH'),'vertices')
for area in bpy.context.screen.areas:
    if area.type=='VIEW_3D':
        area.spaces.active.region_3d.view_location=Vector((0,0,1.85))
        area.spaces.active.region_3d.view_distance=7

