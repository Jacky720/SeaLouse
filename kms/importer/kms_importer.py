import bpy
from ..kms import *
import os
from mathutils import Vector
from ...tri.importer.tri import TRI
from ...util.util import getBoneName, expected_parent_bones
from .rotationWrapperObj import objRotationWrapper
import bmesh

DEFAULT_BONE_LENGTH = 100

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
    # TODO: adjust child location too, without breaking export
    bpy.context.view_layer.objects.active = parent
    child.select_set(True)
    parent.select_set(True)
    bpy.ops.object.parent_set(type="ARMATURE")
    child.select_set(False)
    parent.select_set(False)


def construct_mesh(mesh: KMSMesh, kmsCollection, meshInd: int, meshPos, extract_dir: str, hasHumanBones: bool):
    print(f"Importing mesh {meshInd}, parent {mesh.parentInd}, pos {meshPos}")
    vertices = []
    normals = []
    faces = []
    materialIndices = []
    uvs = []
    uvs2 = []
    uvs3 = []
    weights = []
    #bpy.context.scene.collection.children.link(bpy.data.collections.new("looseCoords"))
    for i, vertexGroup in enumerate(mesh.vertexGroups):
        faceIndexOffset = len(vertices)
        vertices += [(vert.x, vert.y, vert.z) for vert in vertexGroup.vertices]
        #for j, vert in enumerate(vertexGroup.vertices):
        #    target = bpy.data.objects.new(str(j), None)
        #    target.empty_display_size = 0.001
        #    target.location = [vert.x/1000, -vert.z/1000, vert.y/1000]
        #    bpy.data.collections["looseCoords"].objects.link(target)
        normals += [(-nrm.x / 4096, -nrm.y / 4096, -nrm.z / 4096) for nrm in vertexGroup.normals]
        weights += [vert.weight for vert in vertexGroup.vertices]
        if vertexGroup.uvs:
            uvs += [(uv.u / 4096, 1 - uv.v / 4096) for uv in vertexGroup.uvs]
        else:
            uvs += [(0, 0) for _ in range(len(vertexGroup.vertices))]
        if vertexGroup.uvs2:
            uvs2 += [(uv.u / 4096, 1 - uv.v / 4096) for uv in vertexGroup.uvs2]
        else:
            uvs2 += [(0, 0) for _ in range(len(vertexGroup.vertices))]
        if vertexGroup.uvs3:
            uvs3 += [(uv.u / 4096, 1 - uv.v / 4096) for uv in vertexGroup.uvs3]
        else:
            uvs3 += [(0, 0) for _ in range(len(vertexGroup.vertices))]
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
    
    # Bounding box adjustment
    for i, vert in enumerate(vertices):
        if vert[0] < mesh.minPos.x:
            vert = (mesh.minPos.x, vert[1], vert[2])
        elif vert[0] > mesh.maxPos.x:
            vert = (mesh.maxPos.x, vert[1], vert[2])
        if vert[1] < mesh.minPos.y:
            vert = (vert[0], mesh.minPos.y, vert[2])
        elif vert[1] > mesh.maxPos.y:
            vert = (vert[0], mesh.maxPos.y, vert[2])
        if vert[2] < mesh.minPos.z:
            vert = (vert[0], vert[1], mesh.minPos.z)
        elif vert[2] > mesh.maxPos.z:
            vert = (vert[0], vert[1], mesh.maxPos.z)
        vertices[i] = vert
    
    #print("\n".join([str(x[0]) for x in normals[:10]]) + "\n")
    
    objmesh = bpy.data.meshes.new("kmsMesh%d" % meshInd)
    obj = bpy.data.objects.new(objmesh.name, objmesh)
    obj.location = Vector(meshPos)
    #obj.location = Vector((0,0,0))
    obj['flag'] = mesh.flag
    kmsCollection.objects.link(obj)
    objmesh.from_pydata(vertices, [], faces, False)
    if bpy.app.version < (4, 1):
        objmesh.use_auto_smooth = True
    #print("\n".join([str(x.normal) for x in objmesh.loops[:10]]) + "\n")
    objmesh.normals_split_custom_set_from_vertices(normals)
    if bpy.app.version < (4, 1):
        objmesh.calc_normals_split()
    objmesh.update(calc_edges=True)
    #for poly in objmesh.polygons:
    #    poly.use_smooth = True
    #print("\n".join([str(x.vertex_index) + " " + str(x.normal.x) for x in objmesh.loops[:10]]))
    
    # Bone weights
    boneName = getBoneName(meshInd) if hasHumanBones else f"bone{meshInd}"
    obj.vertex_groups.new(name=boneName)
    group = obj.vertex_groups[boneName]
    for i, x in enumerate(weights):
        group.add([i], x / 4096, "REPLACE")
    if mesh.parent: # 2 bones
        parentBoneName = getBoneName(mesh.parentInd) if hasHumanBones else f"bone{mesh.parentInd}"
        parentGroup = obj.vertex_groups.new(name=parentBoneName)
        for i, x in enumerate(weights):
            parentGroup.add([i], 1 - x / 4096, "REPLACE")
    
    if apply_materials(mesh, obj, extract_dir):
        bm = bmesh.new()
        bm.from_mesh(objmesh)
        uv_layer = bm.loops.layers.uv.new("UVMap1")
        #uv_layer = bm.loops.layers.uv.verify()
        #bm.faces.layers.tex.verify()
        for i, face in enumerate(bm.faces):
            face.material_index = materialIndices[i]
            for l in face.loops:
                #luv = l[uv_layer]
                ind = l.vert.index
                #print(l.vert)
                #print(uvs[ind])
                l[uv_layer].uv = Vector(uvs[ind])
        if any(x != (0, 0) for x in uvs2):
            uv_layer2 = bm.loops.layers.uv.new("UVMap2")
            for i, face in enumerate(bm.faces):
                for l in face.loops:
                    ind = l.vert.index
                    l[uv_layer2].uv = Vector(uvs2[ind])
        if any(x != (0, 0) for x in uvs3):
            uv_layer3 = bm.loops.layers.uv.new("UVMap3")
            for i, face in enumerate(bm.faces):
                for l in face.loops:
                    ind = l.vert.index
                    l[uv_layer3].uv = Vector(uvs3[ind])
            
        bm.to_mesh(objmesh)
        bm.free()
    
    return obj

def construct_armature(kms: KMS, kmsName: str, hasHumanBones: bool):
    print("Creating armature")
    amt = bpy.data.armatures.new(kmsName +'Amt')
    ob = bpy.data.objects.new(kmsName, amt)
    ob.name = kmsName
    bpy.data.collections.get(kmsName).objects.link(ob)
    
    ob["bboxMin"] = kms.header.minPos.xyz()
    ob["bboxMax"] = kms.header.maxPos.xyz()
    ob["kmsType"] = kms.header.kmsType
    ob["strcode"] = kms.header.strcode
    ob.location = tuple(kms.header.pos.xyz())
    
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    
    for i, mesh in enumerate(kms.meshes):
        meshPos = mesh.pos
        curMesh = mesh
        while curMesh.parent:
            curMesh = curMesh.parent
            meshPos += curMesh.pos
        bone = amt.edit_bones.new(getBoneName(i) if hasHumanBones else f"bone{i}")
        bone.head = Vector(tuple(meshPos.xyz()))
        bone.tail = bone.head + Vector((0, DEFAULT_BONE_LENGTH, 0))
    
    # Parenting
    bones = amt.edit_bones
    for i, bone in enumerate(bones):
        mesh = kms.meshes[i]
        if mesh.parentInd == -1:
            continue
        bone.parent = bones[mesh.parentInd]
        # Join bones
        if bone.parent.tail == bone.parent.head + Vector((0, DEFAULT_BONE_LENGTH, 0)):
            bone.parent.tail = bone.head
            dist = bone.parent.head - bone.parent.tail
            if abs(dist.x) + abs(dist.y) + abs(dist.z) < 10:
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
    #remapped = open("C:/Users/jackm/AppData/Roaming/Blender Foundation/Blender/3.6/scripts/addons/SeaLouse/tri/importer/ctxrmapping.txt", 'rt')
    #for x in remapped.readlines():
    #    if x.split()[1] == mapName:
    #        mapName = x.split()[0]
    #        break
    if bpy.data.images.get(mapName) is not None:
        return bpy.data.images.get(mapName)
    mapPath = os.path.join(extract_dir, mapName) # "ctxr",
    if not os.path.exists(mapPath):
        return None
    bpy.data.images.load(mapPath)
    return bpy.data.images.get(mapName)

def apply_materials(mesh: KMSMesh, obj, extract_dir: str):
    if mesh.numVertexGroup == 0:
        return False
    
    for vertexGroup in mesh.vertexGroups:
        material = bpy.data.materials.new(obj.name)
        # Save flag as custom property
        material["flag"] = vertexGroup.flag
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
            color_image.name = "g_ColorMap"
            color_image.label = "g_ColorMap"
            links.new(color_image.outputs['Color'], principled.inputs['Base Color'])
            links.new(color_image.outputs['Alpha'], principled.inputs['Alpha'])
        elif vertexGroup.colorMap > 0:
            material["colorMapFallback"] = vertexGroup.colorMap
        
        specularMap = get_texture(extract_dir, vertexGroup.specularMap)
        if specularMap is not None:
            specular_image = nodes.new(type='ShaderNodeTexImage')
            specular_image.location = 0,-60
            specular_image.image = specularMap
            specularMap.colorspace_settings.name = 'Non-Color'
            specular_image.hide = True
            specular_image.name = "g_SpecularMap"
            specular_image.label = "g_SpecularMap"
            if 'Specular' in principled.inputs:
                links.new(specular_image.outputs['Alpha'], principled.inputs['Specular'])
            else:
                links.new(specular_image.outputs['Alpha'], principled.inputs['Specular IOR Level'])
        elif vertexGroup.specularMap > 0:
            material["specularMapFallback"] = vertexGroup.specularMap
        
        if 'Specular' in principled.inputs:
            principled.inputs['Specular'].default_value = 0.0
        else:
            principled.inputs['Specular IOR Level'].default_value = 0.0
        
        envMap = get_texture(extract_dir, vertexGroup.environmentMap)
        if envMap is not None:
            env_image = nodes.new(type='ShaderNodeTexImage')
            env_image.location = 0,-120
            env_image.image = envMap
            if envMap != colorMap:
                envMap.colorspace_settings.name = 'Non-Color'
            env_image.hide = True
            env_image.name = "g_EnvironmentMap"
            env_image.label = "g_EnvironmentMap"
            links.new(env_image.outputs['Alpha'], principled.inputs['Metallic'])
        elif vertexGroup.environmentMap > 0:
            material["environmentMapFallback"] = vertexGroup.environmentMap
        
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
    
    parentBoneList = [mesh.parentInd for mesh in kms.meshes]
    hasHumanBones = parentBoneList[:len(expected_parent_bones)] == expected_parent_bones
    
    bMeshes = []
    for i, mesh in enumerate(kms.meshes):
        meshPos = kms.header.pos
        if i < kms.header.numBones:  # ?? Hair technically has no bone and just uses head pos
            meshPos += mesh.pos
        curMesh = mesh
        while curMesh.parent:
            curMesh = curMesh.parent
            meshPos += curMesh.pos
        bMeshes.append(construct_mesh(mesh, col, i, tuple(meshPos.xyz()), extract_dir, hasHumanBones))
    
    amt = construct_armature(kms, collection_name, hasHumanBones)
    for mesh in bMeshes:
        set_partent(amt, mesh)
    
    objRotationWrapper(amt)
    
    print('Importing finished. ;)')
    return {'FINISHED'}
