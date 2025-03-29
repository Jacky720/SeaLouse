import bpy
from ..kms import *
import os
from mathutils import Vector
from ...tri.importer.tri import TRI
from .rotationWrapperObj import objRotationWrapper
import bmesh

DEFAULT_BONE_LENGTH = 10

# Credit WoefulWolf/Nier2Blender2Nier
def reset_blend():
    #bpy.ops.object.mode_set(mode='OBJECT')
    for collection in bpy.data.collections:
        for obj in collection.objects:
            collection.objects.unlink(obj)
        bpy.data.collections.remove(collection)
    for bpy_data_iter in (bpy.data.objects, bpy.data.meshes, bpy.data.lights, bpy.data.cameras, bpy.data.libraries):
        for id_data in bpy_data_iter:
            bpy_data_iter.remove(id_data)
    for material in bpy.data.materials:
        bpy.data.materials.remove(material)
    for amt in bpy.data.armatures:
        bpy.data.armatures.remove(amt)
    for obj in bpy.data.objects:
        bpy.data.objects.remove(obj)
        obj.user_clear()

# Credit WoefulWolf/Nier2Blender2Nier
def set_partent(parent, child):
    bpy.context.view_layer.objects.active = parent
    child.select_set(True)
    parent.select_set(True)
    bpy.ops.object.parent_set(type="ARMATURE")
    child.select_set(False)
    parent.select_set(False)


def construct_mesh(mesh: KMSMesh, kmsCollection, meshInd: int, meshPos, extract_dir: str):
    print("Importing mesh", meshInd)
    vertices = []
    normals = []
    faces = []
    materialIndices = []
    uvs = []
    weights = []
    for i, vertexGroup in enumerate(mesh.vertexGroups):
        faceIndexOffset = len(vertices)
        vertices += [(vert.x, vert.y, vert.z) for vert in vertexGroup.vertices]
        normals += [(-nrm.x / 4095, -nrm.y / 4095, -nrm.z / 4095) for nrm in vertexGroup.normals]
        weights += [vert.weight for vert in vertexGroup.vertices]
        if vertexGroup.uvs:
            uvs += [(uv.u / 4096, 1 - uv.v / 4096) for uv in vertexGroup.uvs]
        else:
            uvs += [(0, 0) for _ in range(len(vertexGroup.vertices))]
        flip = False
        for j in range(vertexGroup.numVertex):
            if vertexGroup.normals[j].isFace:
                if flip:
                    faces.append((j - 2 + faceIndexOffset, j - 1 + faceIndexOffset, j + faceIndexOffset))
                else:
                    faces.append((j - 2 + faceIndexOffset, j + faceIndexOffset, j - 1 + faceIndexOffset))
                materialIndices.append(i)
                flip = not flip
            else:
                flip = False
    objmesh = bpy.data.meshes.new("kmsMesh%d" % meshInd)
    obj = bpy.data.objects.new(objmesh.name, objmesh)
    obj.location = Vector(meshPos)
    #obj.location = Vector((0,0,0))
    kmsCollection.objects.link(obj)
    objmesh.from_pydata(vertices, [], faces)
    objmesh.normals_split_custom_set_from_vertices(normals)
    objmesh.update(calc_edges=True)
    
    # Bone weights
    obj.vertex_groups.new(name="bone%d" % meshInd)
    group = obj.vertex_groups["bone%d" % meshInd]
    for i, x in enumerate(weights):
        group.add([i], x / 4096, "REPLACE")
    if mesh.parent: # 2 bones
        obj.vertex_groups.new(name="bone%d" % mesh.parentInd)
        parentGroup = obj.vertex_groups["bone%d" % mesh.parentInd]
        for i, x in enumerate(weights):
            parentGroup.add([i], 1 - x / 4096, "REPLACE")
    
    if apply_materials(mesh, obj, extract_dir):
        bm = bmesh.new()
        bm.from_mesh(objmesh)
        #uv_layer = bm.loops.layers.uv.new("UVMap1")
        uv_layer = bm.loops.layers.uv.verify()
        #bm.faces.layers.tex.verify()
        for i, face in enumerate(bm.faces):
            face.material_index = materialIndices[i]
            for l in face.loops:
                #luv = l[uv_layer]
                ind = l.vert.index
                #print(l.vert)
                #print(uvs[ind])
                l[uv_layer].uv = Vector(uvs[ind])
        bm.to_mesh(objmesh)
        bm.free()
    
    objmesh.use_auto_smooth = True
    return obj

def construct_armature(kms: KMS, kmsName: str):
    print("Creating armature")
    amt = bpy.data.armatures.new(kmsName +'Amt')
    ob = bpy.data.objects.new(kmsName, amt)
    ob.name = kmsName
    bpy.data.collections.get(kmsName).objects.link(ob)
    
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    
    for i, mesh in enumerate(kms.meshes):
        meshPos = [mesh.pos.x, mesh.pos.y, mesh.pos.z]
        curMesh = mesh
        while curMesh.parent:
            curMesh = curMesh.parent
            meshPos[0] += curMesh.pos.x
            meshPos[1] += curMesh.pos.y
            meshPos[2] += curMesh.pos.z
        bone = amt.edit_bones.new("bone%d" % i)
        bone.head = Vector(tuple(meshPos))
        bone.tail = bone.head + Vector((0, DEFAULT_BONE_LENGTH, 0))
    
    # Parenting
    bones = amt.edit_bones
    for i, mesh in enumerate(kms.meshes):
        if mesh.parentInd == -1:
            continue
        bone = bones[i]
        bone.parent = bones[mesh.parentInd]
        # Join bones
        if bone.parent.tail == bone.parent.head + Vector((0, DEFAULT_BONE_LENGTH, 0)):
            bone.parent.tail = bone.head
            dist = bone.parent.head - bone.parent.tail
            if abs(dist.x) + abs(dist.y) + abs(dist.z) < DEFAULT_BONE_LENGTH:
                bone.parent.tail += Vector((0, DEFAULT_BONE_LENGTH, 0))
    
    bpy.ops.object.mode_set(mode='OBJECT')
    return ob

def fetch_textures(kms: KMS, kms_file: str) -> int:
    tri_file = kms_file[:-4] + ".tri"
    extract_dir = os.path.split(kms_file)[0]
    extract_dir = os.path.join(extract_dir, "sealouse_extract")
    if not os.path.exists(tri_file):
        kms_dir, tri_name = os.path.split(tri_file)
        kms_parent_dir, region = os.path.split(kms_dir)
        asset_dir = os.path.split(kms_parent_dir)[0]
        tri_file = os.path.join(asset_dir, "tri", region, tri_name)
    if not os.path.exists(tri_file):
        return -1
    
    tri = TRI()
    with open(tri_file, "rb") as f:
        tri.fromFile(f)
    os.makedirs(extract_dir, exist_ok=True)
    tri.dumpTextures(extract_dir)
    return tri.header.numTexture

def get_texture(extract_dir: str, mapID: int) -> bpy.types.Image | None:
    if mapID == 0:
        return None
    mapName = "%d.tga" % mapID
    if bpy.data.images.get(mapName) is not None:
        return bpy.data.images.get(mapName)
    mapPath = os.path.join(extract_dir, mapName)
    if not os.path.exists(mapPath):
        return None
    bpy.data.images.load(mapPath)
    return bpy.data.images.get(mapName)

def apply_materials(mesh: KMSMesh, obj, extract_dir: str):
    if mesh.numVertexGroup == 0:
        return False
    
    for i, vertexGroup in enumerate(mesh.vertexGroups):
        material = bpy.data.materials.new(obj.name)
        # Enable Nodes
        material.use_nodes = True
        # Render properties
        material.blend_method = 'CLIP'
        material.alpha_threshold = 0.05
        # Clear Nodes and Links
        material.node_tree.links.clear()
        material.node_tree.nodes.clear()
        # Recreate Nodes and Links with references
        nodes = material.node_tree.nodes
        links = material.node_tree.links
        # PrincipledBSDF and Ouput Shader
        output = nodes.new(type='ShaderNodeOutputMaterial')
        output.location = 1200,0
        principled = nodes.new(type='ShaderNodeBsdfPrincipled')
        principled.location = 900,0
        output_link = links.new( principled.outputs['BSDF'], output.inputs['Surface'] )
    
        colorMap = get_texture(extract_dir, vertexGroup.colorMap)
        if colorMap is not None:
            color_image = nodes.new(type='ShaderNodeTexImage')
            color_image.location = 0,0
            color_image.image = colorMap
            colorMap.colorspace_settings.name = 'sRGB'
            #colorMap.alpha_mode = "NONE"
            color_image.hide = True
            color_image.label = "g_ColorMap%d" % i
            links.new(color_image.outputs['Color'], principled.inputs['Base Color'])
            links.new(color_image.outputs['Alpha'], principled.inputs['Alpha'])
        
        specularMap = get_texture(extract_dir, vertexGroup.specularMap)
        if specularMap is not None:
            specular_image = nodes.new(type='ShaderNodeTexImage')
            specular_image.location = 0,-60
            specular_image.image = specularMap
            specularMap.colorspace_settings.name = 'Non-Color'
            specular_image.hide = True
            specular_image.label = "g_SpecularMap%d" % i
            links.new(specular_image.outputs['Alpha'], principled.inputs['Specular'])
        
        envMap = get_texture(extract_dir, vertexGroup.colorMap)
        if envMap is not None:
            env_image = nodes.new(type='ShaderNodeTexImage')
            env_image.location = 0,-120
            env_image.image = envMap
            if envMap != colorMap:
                envMap.colorspace_settings.name = 'Non-Color'
            env_image.hide = True
            env_image.label = "g_EnvironmentMap%d" % i
            links.new(env_image.outputs['Alpha'], principled.inputs['Metallic'])
        
        obj.data.materials.append(material)
    return True

def main(kms_file: str, useTri: bool = True):
    kms = KMS()
    with open(kms_file, "rb") as f:
        kms.fromFile(f)
    
    
    extract_dir, kmsname = os.path.split(kms_file) # Split only splits into head and tail, but since we want the last part, we don't need to split the head with kms_file.split(os.sep)
    extract_dir = os.path.join(extract_dir, "sealouse_extract")

    kmsCollection = bpy.data.collections.get("KMS")
    if not kmsCollection:
        kmsCollection = bpy.data.collections.new("KMS")
        bpy.context.scene.collection.children.link(kmsCollection)

    collection_name = kmsname[:-4]
    if bpy.data.collections.get(collection_name): # oops, duplicate
        collection_suffix = 1
        while True:
            if not bpy.data.collections.get("%s.%03d" % (collection_name, collection_suffix)):
                collection_name += ".%03d" % collection_suffix
                break
            collection_suffix += 1
    col = bpy.data.collections.new(collection_name)
    
    kmsCollection.children.link(col)
    #bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[-1]
    
    if useTri:
        fetch_textures(kms, kms_file)
    
    bMeshes = []
    for i, mesh in enumerate(kms.meshes):
        meshPos = [mesh.pos.x, mesh.pos.y, mesh.pos.z]
        curMesh = mesh
        while curMesh.parent:
            curMesh = curMesh.parent
            meshPos[0] += curMesh.pos.x
            meshPos[1] += curMesh.pos.y
            meshPos[2] += curMesh.pos.z
        bMeshes.append(construct_mesh(mesh, col, i, tuple(meshPos), extract_dir))
    
    amt = construct_armature(kms, collection_name)
    for mesh in bMeshes:
        set_partent(amt, mesh)
    
    objRotationWrapper(amt)
    
    print('Importing finished. ;)')
    return {'FINISHED'}
