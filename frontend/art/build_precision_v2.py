"""Precision time-series insert v2. Execute in Blender MCP with the v1 cassette scene active.
Keeps the original scene intact, creates a new scene and a separately versioned asset.
"""
import bpy, math
from mathutils import Vector
source=bpy.context.scene
scene=bpy.data.scenes.new('Time Series Precision V2')
for original in source.objects:
    if original.type=='MESH' and not original.name.startswith(('signal-insert__','precision__')):
        o=original.copy();o.data=original.data.copy();scene.collection.objects.link(o)
bpy.context.window.scene=scene

def material(name,color,metal=.35,rough=.28):
    m=bpy.data.materials.new(name);m.use_nodes=True
    n=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    n.inputs['Base Color'].default_value=(*color,1);n.inputs['Metallic'].default_value=metal;n.inputs['Roughness'].default_value=rough
    return m
alloy=material('Precision_Alloy',(.48,.58,.72),.78,.24)
dark=material('Precision_Recess',(.07,.12,.21),.42,.32)
ceramic=material('Precision_Ceramic',(.67,.76,.88),.18,.32)
blue=material('Precision_Blue',(.07,.19,.43),.6,.23)
cyan=material('Precision_Cyan',(.10,.34,.43),.6,.23)
silver=material('Precision_Silver',(.32,.43,.63),.73,.22)
etching=material('Precision_Etching',(.26,.35,.50),.48,.3)
created=[]
def mesh(name,verts,faces,mat):
    data=bpy.data.meshes.new(name);data.from_pydata(verts,[],faces);data.materials.append(mat);data.update()
    o=bpy.data.objects.new('precision__'+name,data);scene.collection.objects.link(o);created.append(o)
    return o

def box(name,x,y,z,w,d,h,mat,bevel=0):
    verts=[(x+a*w/2,y+b*d/2,z+c*h/2) for a,b,c in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
    o=mesh(name,verts,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],mat)
    if bevel:
        m=o.modifiers.new('Precision edge radius','BEVEL');m.width=bevel;m.segments=3
    return o

def ribbon(name,points,width,depth,mat):
    verts=[];faces=[]
    # Eight-sided bevelled extrusion. Face, bevel and side wall catch separate highlights.
    profile=[(-.5,.30),(-.30,.5),(.30,.5),(.5,.30),(.5,-.30),(.30,-.5),(-.30,-.5),(-.5,-.30)]
    for i,p in enumerate(points):
        a=points[max(0,i-1)];b=points[min(len(points)-1,i+1)];dx=b[0]-a[0];dz=b[2]-a[2];length=math.hypot(dx,dz) or 1
        for u,v in profile:verts.append((p[0]-dz/length*u*width,p[1]+v*depth,p[2]+dx/length*u*width))
        if i:
            for j in range(8):faces.append(((i-1)*8+j,(i-1)*8+(j+1)%8,i*8+(j+1)%8,i*8+j))
    faces.extend([tuple(range(7,-1,-1)),tuple((len(points)-1)*8+j for j in range(8))])
    return mesh(name,verts,faces,mat)

def ring(name,x,y,z,r,inner,depth,mat):
    verts=[];faces=[];n=32
    for dy,radius in [(-depth/2,r),(-depth/2,inner),(depth/2,inner),(depth/2,r)]:
        for i in range(n):
            a=i*math.tau/n;verts.append((x+radius*math.cos(a),y+dy,z+radius*math.sin(a)))
    for j in range(4):
        for i in range(n):faces.append((j*n+i,j*n+(i+1)%n,((j+1)%4)*n+(i+1)%n,((j+1)%4)*n+i))
    return mesh(name,verts,faces,mat)

def wave(t,ch):
    if ch==0:return .105*math.sin(t*11)+.045*math.sin(t*24)+.13*math.exp(-((t-.68)/.09)**2)
    if ch==1:return .06*math.sin(t*19)+.035*math.sin(t*41)+.27*math.exp(-((t-.61)/.05)**2)
    return .068*math.sin(t*43)*(.5+.5*math.sin(t*8)**2)+.075*math.sin(t*20)
for ch,mat in enumerate([blue,cyan,silver]):
    z=2.55-ch*.72
    box('Recessed channel well',0,.014,z,3.60,.032,.60,dark,.025)
    box('Floating ceramic bed',0,-.013,z,3.48,.022,.52,ceramic,.019)
    for off in [-.292,.292]:
        box('Raised aluminium guide',0,-.046,z+off,3.65,.075,.033,alloy,.012)
        box('Guide shadow reveal',0,-.008,z+off-.022,3.57,.018,.012,dark,.003)
    points=[(-1.62+3.24*i/320,-.112,z+wave(i/320,ch)) for i in range(321)]
    ribbon('Sculpted signal band',points,.060,.090,mat)
    # Fine highlight strip on one bevel makes physical depth legible at the fixed camera.
    edge=[(x,y-.047,zz+.022) for x,y,zz in points]
    ribbon('Polished signal crest',edge,.009,.006,alloy)
    for i in range(41):
        x=-1.62+i*.081
        box('Laser-etched tick',x,-.030,z-.21,.004,.006,.055 if i%5==0 else .024,etching)
    for t in [.13,.35,.56,.78]:
        x=-1.62+3.24*t;zz=z+wave(t,ch)
        box('Wave suspension pedestal',x,-.061,zz,.042,.060,.042,dark,.008)
    for x in [-1.91,1.91]:
        box('Connector base',x,-.028,z,.21,.085,.54,dark,.035)
        box('Machined connector cap',x,-.095,z,.17,.065,.48,alloy,.026)
        box('Terminal ceramic inset',x,-.135,z,.115,.018,.28,ceramic,.012)
        for j in range(5):box('Terminal contact',x,-.15,z-.105+j*.0525,.086,.018,.018,mat,.004)
        for dz in [-.19,.19]:
            ring('Countersunk terminal screw',x,-.14,z+dz,.027,.012,.012,alloy)
            box('Screw drive slot',x,-.148,z+dz,.026,.006,.005,dark,.001)
# An integrated data bus below the three instruments.
box('Memory module bed',0,-.018,.54,2.65,.06,.25,dark,.025)
box('Memory module lid',0,-.061,.54,2.51,.034,.20,alloy,.017)
for i in range(28):
    box('Bus contact',-1.13+i*.084,-.092,.54,.035,.028,.12,silver,.006)
for x in [-1.39,1.39]:ring('Bus mounting eye',x,-.07,.54,.051,.022,.025,alloy)
# Bake bevels and merge per material to keep draw calls low without reducing geometry.
bpy.context.view_layer.update()
depsgraph=bpy.context.evaluated_depsgraph_get()
for o in created:
    if o.modifiers:
        old=o.data;o.data=bpy.data.meshes.new_from_object(o.evaluated_get(depsgraph));o.modifiers.clear()
for mat in [alloy,dark,ceramic,blue,cyan,silver,etching]:
    objs=[o for o in scene.objects if o.type=='MESH' and len(o.data.materials) and o.data.materials[0]==mat]
    if not objs:continue
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:o.select_set(True)
    bpy.context.view_layer.objects.active=objs[0]
    if len(objs)>1:bpy.ops.object.join()
    objs[0].name='precision__'+mat.name
bpy.ops.object.select_all(action='SELECT')
bpy.ops.wm.save_as_mainfile(filepath=r'D:\Industrial_Time_Series_Agent\frontend\art\time-series-precision-v2.blend')
bpy.ops.export_scene.gltf(filepath=r'D:\Industrial_Time_Series_Agent\frontend\public\models\time-series-precision-v2.glb',use_selection=True,export_apply=True)
print('Precision V2:',len(scene.objects),'objects;',sum(len(o.data.vertices) for o in scene.objects if o.type=='MESH'),'vertices')
