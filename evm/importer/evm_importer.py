import bpy
from ..evm import *
import os
from mathutils import Vector
from math import radians
from ...tri.tri import TRI
from ...kms.importer.rotationWrapperObj import objRotationWrapper
from ...kms.importer.kms_importer import TextureLoad, make_alpha_multiplier, make_specular_env_multiplier
from ...util.util import getBoneName, expected_parent_bones
import bmesh

DEFAULT_BONE_LENGTH = 10

def vertCoordCheck(vert1: EVMVertex, vert2: EVMVertex):
    return vert1.x == vert2.x and vert1.y == vert2.y and vert1.z == vert2.z

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


def construct_mesh(evm: EVM, evmCollection, extract_dir: str, hasHumanBones: bool, texLoader: TextureLoad):
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
        vertices += [tuple(vert.xyz()) for vert in vertexGroup.vertices]
        #for j, vert in enumerate(vertexGroup.vertices):
        #    target = bpy.data.objects.new(str(j), None)
        #    target.empty_display_size = 0.001
        #    target.location = [vert.x/1000, -vert.z/1000, vert.y/1000]
        #    bpy.data.collections["looseCoords"].objects.link(target)
        normals += [(-nrm.x / 4096, -nrm.y / 4096, -nrm.z / 4096) for nrm in vertexGroup.normals]
        if vertexGroup.uvs:
            uvs += [(uv.u / 4096, 1 - uv.v / 4096) for uv in vertexGroup.uvs]
        else:
            uvs += [(0, 1) for _ in range(vertexGroup.numVertex)]
        if vertexGroup.uvs2:
            uvs2 += [(uv.u / 4096, 1 - uv.v / 4096) for uv in vertexGroup.uvs2]
        else:
            uvs2 += [(0, 1) for _ in range(vertexGroup.numVertex)]
        if vertexGroup.uvs3:
            uvs3 += [(uv.u / 4096, 1 - uv.v / 4096) for uv in vertexGroup.uvs3]
        else:
            uvs3 += [(0, 1) for _ in range(vertexGroup.numVertex)]
        
        # This is ridiculous. The data is duplicated! How can the processor...
        if i == 0:
            flip = False
        elif (vertCoordCheck(evm.meshes[i - 1].vertices[-2], vertexGroup.vertices[0]) and
              vertCoordCheck(evm.meshes[i - 1].vertices[-1], vertexGroup.vertices[1])):
            pass # Retain previous flip
        else:
            flip = False
        
        for j in range(2, vertexGroup.numVertex):
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
    i = 0
    vgroups = obj.vertex_groups
    for vertexGroup in evm.meshes:
        if vertexGroup.weights is None:
            i += vertexGroup.numVertex
            continue
        
        for skinIndex in vertexGroup.skinningTable:
            if skinIndex == 0xff:
                continue
            skinName = getBoneName(skinIndex, evm.header.fingerIndex) if hasHumanBones else f"bone{skinIndex}"
            if not vgroups.get(skinName):
                vgroups.new(name=skinName)
        
        for weight_list in vertexGroup.weights:
            for j in range(vertexGroup.numSkin):
                weight = weight_list.weights[j]
                boneIndex = vertexGroup.skinningTable[weight_list.indices[j] >> 2]
                boneName = getBoneName(boneIndex, evm.header.fingerIndex) if hasHumanBones else f"bone{boneIndex}"
                vgroups[boneName].add([i], weight / 128, "ADD")
            i += 1
    
    if apply_materials(evm, obj, extract_dir, texLoader):
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
        if any(x != (0, 1) for x in uvs2):
            uv_layer2 = bm.loops.layers.uv.new("UVMap2")
            for i, face in enumerate(bm.faces):
                for l in face.loops:
                    ind = l.vert.index
                    l[uv_layer2].uv = Vector(uvs2[ind])
        if any(x != (0, 1) for x in uvs3):
            uv_layer3 = bm.loops.layers.uv.new("UVMap3")
            for i, face in enumerate(bm.faces):
                for l in face.loops:
                    ind = l.vert.index
                    l[uv_layer3].uv = Vector(uvs3[ind])
            
        bm.to_mesh(objmesh)
        bm.free()
    
    return obj

def construct_armature(evm: EVM, evmName: str, hasHumanBones: bool):
    print("Creating armature")
    amt = bpy.data.armatures.new(evmName +'Amt')
    ob = bpy.data.objects.new(evmName, amt)
    ob.name = evmName
    bpy.data.collections.get(evmName).objects.link(ob)
    
    ob["bboxMin"] = evm.header.minPos.xyz()
    ob["bboxMax"] = evm.header.maxPos.xyz()
    #ob["evmType"] = evm.header.evmType
    ob["strcode"] = evm.header.strcode
    ob["flag"] = evm.header.flag
    
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    
    for i, evmBone in enumerate(evm.bones):
        boneName = getBoneName(i, evm.header.fingerIndex) if hasHumanBones else f"bone{i}"
        bone = amt.edit_bones.new(boneName)
        bone.head = Vector(tuple(evmBone.worldPos.xyz()))
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

def apply_materials(evm: EVM, obj, extract_dir: str, texLoader: TextureLoad):
    if evm.header.numMeshes == 0:
        return False
    
    for vertexGroup in evm.meshes:
        material = bpy.data.materials.new(obj.name)
        # Save flag as custom property
        material["flag"] = vertexGroup.flag
        # Enable Nodes
        material.use_nodes = True
        # Render properties
        material.blend_method = 'HASHED'
        material.use_backface_culling = True
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
    
        colorMap = texLoader.get_texture(vertexGroup.colorMap)
        colorMapName = texLoader.get_texture_nice_name(vertexGroup.colorMap)
        isAlphaBlended = colorMap is not None and colorMapName.find("alp") >= 0 and colorMapName.find("ovl") >= 0
        if colorMap is not None:
            color_image = nodes.new(type='ShaderNodeTexImage')
            color_image.location = 0,0
            color_image.image = colorMap
            colorMap.colorspace_settings.name = 'sRGB'
            # If alpha output is disconnected, the RGB values will be multiplied by it 
            # unless alpha_mode is set to "CHANNEL_PACKED"
            colorMap.alpha_mode = "CHANNEL_PACKED"
            color_image.hide = True
            color_image.name = "g_ColorMap"
            color_image.label = "g_ColorMap"
            links.new(color_image.outputs['Color'], principled.inputs['Base Color'])
            
            if isAlphaBlended:
                output_alpha = color_image.outputs['Alpha']
                if texLoader.ctxr_dir:
                    output_alpha = make_alpha_multiplier(material.node_tree, color_image).outputs[0]
                links.new(output_alpha, principled.inputs['Alpha'])
        elif vertexGroup.colorMap > 0:
            material["colorMapFallback"] = vertexGroup.colorMap
        
        specularMap = texLoader.get_texture(vertexGroup.specularMap)
        specularOut = None
        if specularMap is not None:
            specular_image = nodes.new(type='ShaderNodeTexImage')
            specular_image.location = 0,-60
            specular_image.image = specularMap
            specularMap.colorspace_settings.name = 'Non-Color'
            specular_image.hide = True
            specular_image.name = "g_SpecularMap"
            specular_image.label = "g_SpecularMap"
            specularOut = specular_image.outputs['Alpha']

            if texLoader.ctxr_dir:
                specular_mul_node = make_alpha_multiplier(material.node_tree, specular_image, "Specular Alpha Multiplier")
                specularOut = specular_mul_node.outputs[0]
                
            if 'Specular' in principled.inputs:
                links.new(specularOut, principled.inputs['Specular'])
            else:
                links.new(specularOut, principled.inputs['Specular IOR Level'])
        elif vertexGroup.specularMap > 0:
            material["specularMapFallback"] = vertexGroup.specularMap
        
        if 'Specular' in principled.inputs:
            principled.inputs['Specular'].default_value = 0.0
        else:
            principled.inputs['Specular IOR Level'].default_value = 0.0
        
        envMap = texLoader.get_texture(vertexGroup.environmentMap)
        if envMap is not None:
            # If alpha output is disconnected, the RGB values will be multiplied by it 
            # unless alpha_mode is set to "CHANNEL_PACKED"
            envMap.alpha_mode = "CHANNEL_PACKED"

            env_uv = nodes.new(type='ShaderNodeTexCoord')
            env_uv.location = -320,-120
            env_uv.hide = True

            env_mapping = nodes.new(type='ShaderNodeMapping')
            env_mapping.location = -160,-120
            env_mapping.inputs['Rotation'].default_value[2] = radians(90)
            env_mapping.hide = True
            
            env_image = nodes.new(type='ShaderNodeTexEnvironment')
            env_image.location = 0,-120
            env_image.image = envMap
            # Environment maps are supposed to contain colors
            # if envMap != colorMap: 
            #     envMap.colorspace_settings.name = 'Non-Color'
            env_image.hide = True
            env_image.name = "g_EnvironmentMap"
            env_image.label = "g_EnvironmentMap"
            environmentOut = env_image.outputs['Color']

            links.new(env_uv.outputs['Reflection'], env_mapping.inputs['Vector'])
            links.new(env_mapping.outputs['Vector'], env_image.inputs['Vector'])
            
            # Truer to the PS2 look, environment maps are rendered as an additive pass
            
            if specularMap is not None:
                env_mul = make_specular_env_multiplier(material.node_tree,env_image,specularOut)
                environmentOut = env_mul.outputs[2]  # Color Result
            
            if 'Emission Color' in principled.inputs:
                links.new(environmentOut, principled.inputs['Emission Color'])
            else:
                links.new(environmentOut, principled.inputs['Emission'])
                
            principled.inputs['Emission Strength'].default_value = 1.0
            
            # output_alpha = env_image.outputs['Alpha']
            # if texLoader.ctxr_dir:
            #     output_alpha = make_alpha_multiplier(material.node_tree, env_image).outputs[0]
            # links.new(output_alpha, principled.inputs['Metallic'])
        elif vertexGroup.environmentMap > 0:
            material["environmentMapFallback"] = vertexGroup.environmentMap
        
        obj.data.materials.append(material)
    return True

def main(evm_file: str, ctxr_path: str = None, overwrite_existing: bool = False):
    evm = EVM()
    with open(evm_file, "rb") as f:
        evm.fromFile(f)
    
    
    extract_dir, evmname = os.path.split(evm_file)
    extract_dir = os.path.join(extract_dir, "sealouse_extract")

    evmCollection = bpy.data.collections.get("EVM")
    if not evmCollection:
        evmCollection = bpy.data.collections.new("EVM")
        bpy.context.scene.collection.children.link(evmCollection)

    collection_name = evmname[:-4]
    if bpy.data.collections.get(collection_name): # oops, duplicate
        collection_suffix = 1
        while bpy.data.collections.get(f"{collection_name}.{collection_suffix:03}"):
            collection_suffix += 1
        collection_name += f".{collection_suffix:03}"
    col = bpy.data.collections.new(collection_name)
    
    evmCollection.children.link(col)
    #bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[-1]
    
    parentBoneList = [bone.parentInd for bone in evm.bones]
    hasHumanBones = parentBoneList[:len(expected_parent_bones)] == expected_parent_bones
    
    texLoader = TextureLoad(extract_dir, ctxr_path, overwrite_existing)
    
    mesh = construct_mesh(evm, col, extract_dir, hasHumanBones, texLoader)
    amt = construct_armature(evm, collection_name, hasHumanBones)
    set_partent(amt, mesh)
    
    objRotationWrapper(amt)
    
    print('Importing finished. ;)')
    return {'FINISHED'}
