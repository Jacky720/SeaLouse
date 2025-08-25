from __future__ import annotations
import bpy
from ..kms import *
import os
from mathutils import Vector
from math import radians
from ...ctxr.ctxr import CTXR, ctxr_lookup_path
from ...util.util import getBoneName, expected_parent_bones, replaceExt
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


def construct_mesh(mesh: KMSMesh, kmsCollection, meshInd: int, meshPos, extract_dir: str, hasHumanBones: bool, texLoader: TextureLoad):
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
    
    if apply_materials(mesh, obj, extract_dir, texLoader):
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


class TextureLoad:
    extract_dir: str
    ctxr_dir: str | None  # ctxr load folder if using ctxr
    ctxr_name_lookup: dict
    overwrite_existing: bool

    def __init__(self, extract_dir: str, ctxr_dir: str = None, overwrite_existing: bool = False):
        self.extract_dir = extract_dir
        self.ctxr_dir = ctxr_dir
        self.ctxr_name_lookup = {}
        self.overwrite_existing = overwrite_existing
        if not ctxr_dir:
            return
        
        with open(ctxr_lookup_path, "rt") as f:
            for line in f.readlines():
                tga_num = os.path.splitext(line.split()[1])[0]
                self.ctxr_name_lookup[int(tga_num)] = line.split()[2]
    
    def get_texture(self, mapID: int) -> bpy.types.Image | None:
        if mapID == 0:
            return None
        mapName = f"{mapID}.tga"
        if mapID in self.ctxr_name_lookup:
            mapName = replaceExt(self.ctxr_name_lookup[mapID], "dds")
        
        if bpy.data.images.get(mapName) is not None:
            return bpy.data.images.get(mapName)
        
        mapPath = os.path.join(self.extract_dir, mapName)
        
        if not os.path.exists(mapPath) or self.overwrite_existing:
            if not self.ctxr_dir:
                return None
            # Load ctxr
            ctxr_path = os.path.join(self.ctxr_dir, replaceExt(mapName, "ctxr"))
            if not os.path.exists(ctxr_path):
                return None
            print("Extracting", ctxr_path, "to DDS")
            ctxr = CTXR()
            with open(ctxr_path, "rb") as f:
                ctxr.fromFile(f)
            dds = ctxr.convertDDS()
            with open(mapPath, "wb") as f:
                dds.writeToFile(f)
        
        bpy.data.images.load(mapPath)
        return bpy.data.images.get(mapName)

def make_alpha_multiplier(node_tree, image_node):
    nodes = node_tree.nodes
    links = node_tree.links
    alpha_multiplier = nodes.new(type='ShaderNodeMath')
    alpha_multiplier.label = 'Multiply Alpha'
    alpha_multiplier.location = (image_node.location[0] + 300, image_node.location[1])
    alpha_multiplier.operation = 'MULTIPLY'
    alpha_multiplier.inputs[1].default_value = 2.0
    links.new(image_node.outputs['Alpha'], alpha_multiplier.inputs[0])
    alpha_multiplier.hide = True
    return alpha_multiplier

def make_specular_env_multiplier(node_tree, env_node, specular_node):
    nodes = node_tree.nodes
    links = node_tree.links
    env_multiplier = nodes.new(type='ShaderNodeMix')
    env_multiplier.name = 'Multiply EnvMap'
    env_multiplier.label = 'Multiply EnvMap'
    env_multiplier.location = (env_node.location[0] + 300, env_node.location[1])
    env_multiplier.hide = True
    
    env_multiplier.data_type = "RGBA"
    env_multiplier.blend_type = 'MULTIPLY'
    env_multiplier.inputs['Factor'].default_value = 1.0
    links.new(specular_node.outputs[0], env_multiplier.inputs['A'])
    links.new(env_node.outputs['Color'], env_multiplier.inputs['B'])
    return env_multiplier

def apply_materials(mesh: KMSMesh, obj, extract_dir: str, texLoader: TextureLoad):
    if mesh.numVertexGroup == 0:
        return False
    
    for vertexGroup in mesh.vertexGroups:
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
        isAlphaBlended = colorMap is not None and colorMap.name.find("alp") >= 0 and colorMap.name.find("ovl") >= 0
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
        if specularMap is not None:
            specular_image = nodes.new(type='ShaderNodeTexImage')
            specular_image.location = 0,-60
            specular_image.image = specularMap
            specularMap.colorspace_settings.name = 'Non-Color'
            specular_image.hide = True
            specular_image.name = "g_SpecularMap"
            specular_image.label = "g_SpecularMap"
            output_alpha = specular_image.outputs['Alpha']
            if texLoader.ctxr_dir:
                output_alpha = make_alpha_multiplier(material.node_tree, specular_image).outputs[0]
            if 'Specular' in principled.inputs:
                links.new(output_alpha, principled.inputs['Specular'])
            else:
                links.new(output_alpha, principled.inputs['Specular IOR Level'])
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
            output_color = env_image.outputs['Color']
            
            links.new(env_uv.outputs['Reflection'], env_mapping.inputs['Vector'])
            links.new(env_mapping.outputs['Vector'], env_image.inputs['Vector'])

            # Truer to the PS2 look, environment maps are rendered as an additive pass
            
            if specularMap is not None:
                specular_mul = nodes['Specular Alpha Multiplier']
                env_mul = make_specular_env_multiplier(material.node_tree,env_image,specular_mul)
                links.new(env_mul.outputs['Result'], principled.inputs['Emission Color'])
            else:
                links.new(output_color, principled.inputs['Emission Color'])
            
            
            principled.inputs['Emission Strength'].default_value = 1.0
            
            # output_alpha = env_image.outputs['Alpha']
            # if texLoader.ctxr_dir:
            #     output_alpha = make_alpha_multiplier(material.node_tree, env_image).outputs[0]
            # links.new(output_alpha, principled.inputs['Metallic'])
        elif vertexGroup.environmentMap > 0:
            material["environmentMapFallback"] = vertexGroup.environmentMap
        
        obj.data.materials.append(material)
    return True

def main(kms_file: str, ctxr_path: str = None, overwrite_existing: bool = False):
    kms = KMS()
    with open(kms_file, "rb") as f:
        kms.fromFile(f)
    
    
    extract_dir, kmsname = os.path.split(kms_file)
    extract_dir = os.path.join(extract_dir, "sealouse_extract")

    kmsCollection = bpy.data.collections.get("KMS")
    if not kmsCollection:
        kmsCollection = bpy.data.collections.new("KMS")
        bpy.context.scene.collection.children.link(kmsCollection)

    collection_name = os.path.splitext(kmsname)[0]
    if bpy.data.collections.get(collection_name): # oops, duplicate
        collection_suffix = 1
        while bpy.data.collections.get(f"{collection_name}.{collection_suffix:03}"):
            collection_suffix += 1
        collection_name += f".{collection_suffix:03}"
    col = bpy.data.collections.new(collection_name)
    
    kmsCollection.children.link(col)
    #bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[-1]
    
    parentBoneList = [mesh.parentInd for mesh in kms.meshes]
    hasHumanBones = parentBoneList[:len(expected_parent_bones)] == expected_parent_bones
    
    texLoader = TextureLoad(extract_dir, ctxr_path, overwrite_existing)
    
    bMeshes = []
    for i, mesh in enumerate(kms.meshes):
        meshPos = kms.header.pos
        if i < kms.header.numBones:  # ?? Hair technically has no bone and just uses head pos
            meshPos += mesh.pos
        curMesh = mesh
        while curMesh.parent:
            curMesh = curMesh.parent
            meshPos += curMesh.pos
        bMeshes.append(construct_mesh(mesh,
                                      col,
                                      i,
                                      tuple(meshPos.xyz()),
                                      extract_dir,
                                      hasHumanBones,
                                      texLoader))
    
    amt = construct_armature(kms, collection_name, hasHumanBones)
    for mesh in bMeshes:
        set_partent(amt, mesh)
    
    objRotationWrapper(amt)
    
    print('Importing finished. ;)')
    return {'FINISHED'}
