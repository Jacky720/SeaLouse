import bpy
from ..evm import *
import os
from mathutils import Vector
from ...tri.importer.tri import TRI
from ...kms.importer.rotationWrapperObj import objRotationWrapper
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


def construct_mesh(evm: EVM, evmCollection, extract_dir: str):
    print("Importing mesh")
    vertices = []
    normals = []
    faces = []
    materialIndices = []
    uvs = []
    uvs2 = []
    uvs3 = []
    weights = []
    boneIndices = []
    #bpy.context.scene.collection.children.link(bpy.data.collections.new("looseCoords"))
    for i, vertexGroup in enumerate(evm.meshes):
        faceIndexOffset = len(vertices)
        vertices += [(vert.x, vert.y, vert.z) for vert in vertexGroup.vertices]
        #for j, vert in enumerate(vertexGroup.vertices):
        #    target = bpy.data.objects.new(str(j), None)
        #    target.empty_display_size = 0.001
        #    target.location = [vert.x/1000, -vert.z/1000, vert.y/1000]
        #    bpy.data.collections["looseCoords"].objects.link(target)
        normals += [(-nrm.x / 4096, -nrm.y / 4096, -nrm.z / 4096) for nrm in vertexGroup.normals]
        if vertexGroup.uvs:
            uvs += [(uv.u / 4096, 1 - uv.v / 4096) for uv in vertexGroup.uvs]
        else:
            uvs += [(0, 0) for _ in range(vertexGroup.numVertex)]
        if vertexGroup.uvs2:
            uvs2 += [(uv.u / 4096, 1 - uv.v / 4096) for uv in vertexGroup.uvs2]
        else:
            uvs2 += [(0, 0) for _ in range(vertexGroup.numVertex)]
        if vertexGroup.uvs3:
            uvs3 += [(uv.u / 4096, 1 - uv.v / 4096) for uv in vertexGroup.uvs3]
        else:
            uvs3 += [(0, 0) for _ in range(vertexGroup.numVertex)]
        flip = False
        for j in range(vertexGroup.numVertex):
            if vertexGroup.vertices[j].isFace:
                if flip:
                    faces.append((j - 2 + faceIndexOffset, j - 1 + faceIndexOffset, j + faceIndexOffset))
                else:
                    faces.append((j - 2 + faceIndexOffset, j + faceIndexOffset, j - 1 + faceIndexOffset))
                materialIndices.append(i)
                flip = not flip
            else:
                flip = False
    
    # Bounding box adjustment
    """
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
    """
    #print("\n".join([str(x) for x in normals]))
    
    objmesh = bpy.data.meshes.new("evmMesh")
    obj = bpy.data.objects.new(objmesh.name, objmesh)
    #obj.location = Vector(meshPos)
    obj.location = Vector((0,0,0))
    obj.scale = Vector((1/16,1/16,1/16))
    evmCollection.objects.link(obj)
    objmesh.from_pydata(vertices, [], faces)
    objmesh.normals_split_custom_set_from_vertices(normals)
    objmesh.update(calc_edges=True)
    #print("\n".join([str(x.normal) for x in objmesh.vertices]))
    
    # Bone weights
    i = 0
    vgroups = obj.vertex_groups
    for vertexGroup in evm.meshes:
        if vertexGroup.weights is None:
            i += vertexGroup.numVertex
            continue
        
        for skinIndex in vertexGroup.skinningTable:
            if skinIndex == 0xff:
                continue
            skinName = "bone%d" % skinIndex
            if not vgroups.get(skinName):
                vgroups.new(name=skinName)
        
        for weight_list in vertexGroup.weights:
            for j in range(vertexGroup.numSkin):
                weight = weight_list.weights[j]
                boneIndex = vertexGroup.skinningTable[weight_list.indices[j] >> 2]
                vgroups["bone%d" % boneIndex].add([i], weight / 128, "ADD")
            i += 1
    
    if apply_materials(evm, obj, extract_dir):
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
    
    objmesh.use_auto_smooth = True
    return obj

def construct_armature(evm: EVM, evmName: str):
    print("Creating armature")
    amt = bpy.data.armatures.new(evmName +'Amt')
    ob = bpy.data.objects.new(evmName, amt)
    ob.name = evmName
    bpy.data.collections.get(evmName).objects.link(ob)
    
    ob["bboxMin"] = [evm.header.minPos.x, evm.header.minPos.y, evm.header.minPos.z]
    ob["bboxMax"] = [evm.header.maxPos.x, evm.header.maxPos.y, evm.header.maxPos.z]
    #ob["evmType"] = evm.header.evmType
    ob["strcode"] = evm.header.strcode
    ob["flag"] = evm.header.flag
    
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    
    for i, evmBone in enumerate(evm.bones):
        bone = amt.edit_bones.new("bone%d" % i)
        bone.head = Vector((evmBone.worldPos.x, evmBone.worldPos.y, evmBone.worldPos.z))
        bone.tail = bone.head + Vector((0, DEFAULT_BONE_LENGTH, 0))
    
    # Parenting
    bones = amt.edit_bones
    for i, evmBone in enumerate(evm.bones):
        if evmBone.parentInd == -1:
            continue
        bone = bones[i]
        bone.parent = bones[evmBone.parentInd]
        # Join bones
        if bone.parent.tail == bone.parent.head + Vector((0, DEFAULT_BONE_LENGTH, 0)):
            bone.parent.tail = bone.head
            dist = bone.parent.head - bone.parent.tail
            if abs(dist.x) + abs(dist.y) + abs(dist.z) < DEFAULT_BONE_LENGTH:
                bone.parent.tail += Vector((0, DEFAULT_BONE_LENGTH, 0))
    
    bpy.ops.object.mode_set(mode='OBJECT')
    return ob

def fetch_textures(evm: EVM, evm_file: str) -> int:
    tri_file = evm_file[:-4] + ".tri"
    extract_dir = os.path.split(evm_file)[0]
    extract_dir = os.path.join(extract_dir, "sealouse_extract")
    if not os.path.exists(tri_file):
        evm_dir, tri_name = os.path.split(tri_file)
        evm_parent_dir, region = os.path.split(evm_dir)
        asset_dir = os.path.split(evm_parent_dir)[0]
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

def apply_materials(evm: EVM, obj, extract_dir: str):
    if evm.header.numMeshes == 0:
        return False
    
    for vertexGroup in evm.meshes:
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
            links.new(specular_image.outputs['Alpha'], principled.inputs['Specular'])
        elif vertexGroup.specularMap > 0:
            material["specularMapFallback"] = vertexGroup.specularMap
            principled.inputs['Specular'].default_value = 0.0
        else:
            principled.inputs['Specular'].default_value = 0.0
        
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

def main(evm_file: str, useTri: bool = True):
    evm = EVM()
    with open(evm_file, "rb") as f:
        evm.fromFile(f)
    
    
    extract_dir, evmname = os.path.split(evm_file) # Split only splits into head and tail, but since we want the last part, we don't need to split the head with evm_file.split(os.sep)
    extract_dir = os.path.join(extract_dir, "sealouse_extract")

    evmCollection = bpy.data.collections.get("EVM")
    if not evmCollection:
        evmCollection = bpy.data.collections.new("EVM")
        bpy.context.scene.collection.children.link(evmCollection)

    collection_name = evmname[:-4]
    if bpy.data.collections.get(collection_name): # oops, duplicate
        collection_suffix = 1
        while True:
            if not bpy.data.collections.get("%s.%03d" % (collection_name, collection_suffix)):
                collection_name += ".%03d" % collection_suffix
                break
            collection_suffix += 1
    col = bpy.data.collections.new(collection_name)
    
    evmCollection.children.link(col)
    #bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[-1]
    
    if useTri:
        fetch_textures(evm, evm_file)
    
    mesh = construct_mesh(evm, col, extract_dir)
    amt = construct_armature(evm, collection_name)
    set_partent(amt, mesh)
    
    objRotationWrapper(amt)
    
    print('Importing finished. ;)')
    return {'FINISHED'}
