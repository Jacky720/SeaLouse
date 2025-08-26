import bpy
from ..kms import *
from ...util.util import getBoneName, getBoneIndex, replaceExt
from ...util.util import getVertWeight as rawVertWeight
from ...ctxr.ctxr import DDS, ctxr_lookup_path
import os
from mathutils import Vector


class MeshExportHelper:
    obj: bpy.types.Object
    mesh: bpy.types.Mesh
    bone: bpy.types.Bone
    
    def __init__(self, obj: bpy.types.Object, bone: bpy.types.Bone):
        self.obj = obj
        if obj.type != 'MESH':
            raise Exception(f"Invalid object {obj.name} with type {obj.type} passed to MeshExportHelper")
        self.mesh = obj.data
        self.bone = bone
    
    def getVertWeight(self, vert) -> int:
        return int(rawVertWeight(vert, self.obj, self.bone.name) * 4096)
    
    def kmsVertFromVert(self, vert) -> KMSVertex:
        return KMSVertex(round(vert.co.x), round(vert.co.y), round(vert.co.z), self.getVertWeight(vert))
    
    def kmsVertFromIndex(self, index) -> KMSVertex:
        return self.kmsVertFromVert(self.mesh.vertices[index])

def kmsNormFromLoop(loop, isFace: bool) -> KMSNormal:
    return KMSNormal(loop.normal.x * -4096, loop.normal.y * -4096, loop.normal.z * -4096, isFace)

def kmsUvFromLayerAndLoop(mesh, uvLayer: int, loopIndex: int) -> KMSUv:
    uv = mesh.uv_layers[uvLayer].uv[loopIndex].vector
    return KMSUv(uv.x * 4096, (1 - uv.y) * 4096)


class TextureSave:
    ctxr_id_lookup: dict
    textures_to_save: set[bpy.types.Image]

    def __init__(self):
        self.ctxr_id_lookup = {}
        self.textures_to_save = set()
        
        with open(ctxr_lookup_path, "rt") as f:
            for line in f.readlines():
                tga_num = os.path.splitext(line.split()[1])[0]
                self.ctxr_id_lookup[line.split()[2]] = int(tga_num)
    
    def get_map(self, mat: bpy.types.Material, mapType: str) -> int:
        nodes = mat.node_tree.nodes
        mapType = mapType.lower()
        if "map" not in mapType:
            mapType += "Map"
        mapType = mapType.replace("map", "Map")
        
        mapID = 0
        matchImage = None
        
        if nodes.get(f"g_{mapType.capitalize()}") is not None:
            matchImage = nodes[f"g_{mapType.capitalize()}"].image
        elif mat.get(f"{mapType}Fallback") is not None:
            mapID = mat[f"{mapType}Fallback"]
        if not matchImage and "Principled BSDF" in nodes:  # Check anything
            principled = nodes["Principled BSDF"]
            if mapType == 'colorMap':
                inputName = "Base Color"
            elif mapType == 'specularMap':
                if "Specular" in principled.inputs:
                    inputName = "Specular"
                else:
                    inputName = "Specular IOR Level"
            elif mapType == 'environmentMap':
                if "Emission" in principled.inputs:
                    inputName = "Emission"
                else:
                    inputName = "Emission Color"
            else:
                return mapID
            
            if len(principled.inputs[inputName].links) != 1:
                return mapID
            fromNode = principled.inputs[inputName].links[0].from_node
            if fromNode.bl_idname == 'ShaderNodeTexImage':
                matchImage = fromNode.image
            elif fromNode.bl_idname == 'ShaderNodeMath' and len(fromNode.inputs[0].links) == 1:
                matchImage = fromNode.inputs[0].links[0].from_node.image
            elif fromNode.bl_idname == 'ShaderNodeMix' and len(fromNode.inputs[7].links) == 1 and \
              fromNode.inputs[7].links[0].from_node.bl_idname == 'ShaderNodeTexImage':
                matchImage = fromNode.inputs[7].links[0].from_node.image
                # Also consider swapping A and B inputs (very unlikely, but not hard to cover our bases)
            elif fromNode.bl_idname == 'ShaderNodeMix' and len(fromNode.inputs[6].links) == 1 and \
              fromNode.inputs[6].links[0].from_node.bl_idname == 'ShaderNodeTexImage':
                matchImage = fromNode.inputs[6].links[0].from_node.image
            else:
                return mapID
        
        if matchImage is not None:
            matchImageName, matchImageExt = os.path.splitext(matchImage.name)
            # TGA detection takes priority over fallback ID
            if matchImageName.isnumeric() and matchImageExt == ".tga":
                mapID = int(matchImageName)
            elif matchImageExt == ".dds" and matchImageName + ".png" in self.ctxr_id_lookup:
                self.textures_to_save.add(matchImage)
                # DDS detection does not have priority over fallback ID
                if not mapID:
                    mapID = self.ctxr_id_lookup[matchImageName + ".png"]
        
        return mapID
    
    def save_textures(self, extract_dir: str):
        for image in self.textures_to_save:
            ctxr_name = replaceExt(image.name, "ctxr")
            print("Packing image", ctxr_name)
            if not os.path.exists(image.filepath_from_user()):
                print("Error: Could not locate image on disk, skipping.")
                continue
            with open(image.filepath_from_user(), "rb") as f:
                dds = DDS().fromFile(f)
            ctxr = dds.convertCTXR()
            if "_ovl_sub_alp.bmp" in ctxr_name:
                # Specular maps/transparent textures need different parameters
                ctxr.header.unknown4 = [0, 0, 0, 2, 2, 2, 0, 2, 2, 2, 0x68, 0xff, 0xff, 0, 0, 0, 0, 0]
            with open(os.path.join(extract_dir, ctxr_name), "wb") as f:
                ctxr.writeToFile(f)

def main(kms_file: str, collection_name: str, ctxr_dir: str = None):
    kms = KMS()
    
    collection = bpy.data.collections[collection_name]
    
    amt = [x for x in collection.all_objects if x.type == "ARMATURE"][0]
    kms.header.kmsType = amt["kmsType"]
    kms.header.strcode = amt["strcode"]
    kms.header.minPos = KMSVector3().set(amt["bboxMin"])
    kms.header.maxPos = KMSVector3().set(amt["bboxMax"])
    kms.header.pos = KMSVector3().set(amt.location)
    
    bpy.ops.object.select_all(action='DESELECT')
    amt.select_set(True)
    bpy.context.view_layer.objects.active = amt
    bpy.ops.object.mode_set(mode='EDIT')
    bones = amt.data.edit_bones
    forceBoneCount = len(bones)
    
    texSave = TextureSave()
    
    for obj in collection.all_objects:
        if obj.type != "MESH":
            continue
        print("Exporting", obj.name)
        # For now, let's assume direct re-export (so meshes and bones are still tightly linked)
        #kms.header.numMesh += 1
        #kms.header.numBones += 1
        mesh = obj.data
        if bpy.app.version < (4, 1):
            mesh.calc_normals_split()
        
        kmsMesh = KMSMesh()
        kmsMesh.flag = obj['flag'] if 'flag' in obj else 1
        
        meshIndex = int(obj.name.split('Mesh')[1])
        bone = bones.get(getBoneName(meshIndex)) or bones[meshIndex]
        if bone.name == 'head_2' and len(bones) == 22:
            # Hair doesn't actually get a bone in KMS?
            forceBoneCount = 21
        print(f"Making mesh for bone {bone.name}, pos {tuple(bone.head)}")
        kmsMesh.pos.set(bone.head)
        kmsMesh.minPos.set(obj.bound_box[0])
        kmsMesh.maxPos.set(obj.bound_box[6])

        kmsMesh.parentInd = -1
        if bone.parent:
            kmsMesh.parentInd = getBoneIndex(bone.parent.name)
            kmsMesh.parent = kms.meshes[kmsMesh.parentInd]
        # Recursively fix position
        curMesh = kmsMesh.parent
        while curMesh:
            kmsMesh.pos -= curMesh.pos
            curMesh = curMesh.parent
        
        kmsMesh.pos -= kms.header.pos
        
        # Create vertex groups from materials
        for materialSlot in obj.material_slots:
            #kmsMesh.numVertexGroup += 1
            mat = materialSlot.material
            
            vertexGroup = KMSVertexGroup()
            if "flag" in mat:
                vertexGroup.flag = mat["flag"]
            elif obj.name == "kmsMesh0":
                vertexGroup.flag = 760
            else:
                vertexGroup.flag = 761
            
            vertexGroup.colorMap = texSave.get_map(mat, "colorMap")
            vertexGroup.specularMap = texSave.get_map(mat, "specularMap")
            vertexGroup.environmentMap = texSave.get_map(mat, "environmentMap")

            if len(mesh.uv_layers) > 0:
                vertexGroup.uvs = []
            if len(mesh.uv_layers) > 1:
                vertexGroup.uvs2 = []
            if len(mesh.uv_layers) > 2:
                vertexGroup.uvs3 = []
                
            kmsMesh.vertexGroups.append(vertexGroup)
        
        allVertsWritten: List[List[int]] = [[] for _ in range(len(kmsMesh.vertexGroups))]
        helper = MeshExportHelper(obj, bone)
        flip = False
        for polygon in mesh.polygons:
            assert(polygon.loop_total == 3) # Not triangulated!
            polyMat = polygon.material_index
            vertexGroup = kmsMesh.vertexGroups[polyMat]
            vertsWritten = allVertsWritten[polyMat]
            loopIndices = list(range(polygon.loop_start, polygon.loop_start + 3))
            loopIndices = [loopIndices[0], loopIndices[2], loopIndices[1]]
            vertexIndices = [mesh.loops[i].vertex_index for i in loopIndices]
            if flip:
                other_check_index = 1
                compress_add_index = 2
            else:
                other_check_index = 2
                compress_add_index = 1
            if len(vertsWritten) > 0 and \
               vertexIndices[other_check_index] == vertsWritten[-1] and \
               vertexIndices[0] == vertsWritten[-2]:
                # Optimize!
                vertsWritten += [vertexIndices[compress_add_index]]
                vertexGroup.vertices += [helper.kmsVertFromIndex(vertexIndices[compress_add_index])]
                vertexGroup.normals += [kmsNormFromLoop(mesh.loops[loopIndices[compress_add_index]], True)]
                if vertexGroup.uvs is not None:
                    vertexGroup.uvs += [kmsUvFromLayerAndLoop(mesh, 0, loopIndices[compress_add_index])]
                if vertexGroup.uvs2 is not None:
                    vertexGroup.uvs2 += [kmsUvFromLayerAndLoop(mesh, 1, loopIndices[compress_add_index])]
                if vertexGroup.uvs3 is not None:
                    vertexGroup.uvs3 += [kmsUvFromLayerAndLoop(mesh, 2, loopIndices[compress_add_index])]
                flip = not flip
            else:
                # add all three :(
                vertsWritten += vertexIndices
                vertexGroup.vertices += [helper.kmsVertFromIndex(vert) for vert in vertexIndices]
                vertexGroup.normals += [
                    kmsNormFromLoop(mesh.loops[loopIndices[0]], False),
                    kmsNormFromLoop(mesh.loops[loopIndices[1]], False),
                    kmsNormFromLoop(mesh.loops[loopIndices[2]], True)
                ]
                if vertexGroup.uvs is not None:
                    vertexGroup.uvs += [
                        kmsUvFromLayerAndLoop(mesh, 0, loopIndices[0]),
                        kmsUvFromLayerAndLoop(mesh, 0, loopIndices[1]),
                        kmsUvFromLayerAndLoop(mesh, 0, loopIndices[2])
                    ]
                if vertexGroup.uvs2 is not None:
                    vertexGroup.uvs2 += [
                        kmsUvFromLayerAndLoop(mesh, 1, loopIndices[0]),
                        kmsUvFromLayerAndLoop(mesh, 1, loopIndices[1]),
                        kmsUvFromLayerAndLoop(mesh, 1, loopIndices[2])
                    ]
                if vertexGroup.uvs3 is not None:
                    vertexGroup.uvs3 += [
                        kmsUvFromLayerAndLoop(mesh, 2, loopIndices[0]),
                        kmsUvFromLayerAndLoop(mesh, 2, loopIndices[1]),
                        kmsUvFromLayerAndLoop(mesh, 2, loopIndices[2])
                    ]
                flip = False
        
        for vertexGroup in kmsMesh.vertexGroups:
            # Delete null UVs
            if vertexGroup.uvs and all((uv.u, uv.v) == (0, 4096) for uv in vertexGroup.uvs):
                vertexGroup.uvs = None
            if vertexGroup.uvs2 and all((uv.u, uv.v) == (0, 4096) for uv in vertexGroup.uvs2):
                vertexGroup.uvs2 = None
            if vertexGroup.uvs3 and all((uv.u, uv.v) == (0, 4096) for uv in vertexGroup.uvs3):
                vertexGroup.uvs3 = None
        
        obj['kmsVertSideChannel'] = sum(allVertsWritten, []) # flatten
        kms.meshes.append(kmsMesh)
    
    bpy.ops.object.mode_set(mode='OBJECT')
    
    if ctxr_dir:
        print("Saving new CTXRs...")
        texSave.save_textures(ctxr_dir)
        print("CTXR COMPLETE :)")
    
    with open(kms_file, "wb") as f:
        kms.writeToFile(f, forceBoneCount=forceBoneCount)
    return {'FINISHED'}
