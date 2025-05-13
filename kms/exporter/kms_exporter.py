import bpy
from ..kms import *
import os
from mathutils import Vector

def kmsUvFromLayerAndLoop(obj, uvLayer: int, loopIndex: int) -> KMSUv:
    uv = obj.data.uv_layers[uvLayer].uv[loopIndex].vector
    return KMSUv(uv.x * 4096, (1 - uv.y) * 4096)

def getVertWeight(vert) -> int:
    if vert.groups[0].group == 0: # weight is correct
        return int(vert.groups[0].weight * 4096)
    if len(vert.groups) == 2: # weights are in wrong order (may be impossible, handle anyway)
        return int(vert.groups[1].weight * 4096)
    return 0 # vertex is only weighted to parent

def main(kms_file: str, collection_name: str):
    kms = KMS()
    
    collection = bpy.data.collections[collection_name]
    
    amt = [x for x in collection.all_objects if x.type == "ARMATURE"][0]
    kms.header.kmsType = amt["kmsType"]
    kms.header.strcode = amt["strcode"]
    kms.header.minPos = KMSVector3(amt["bboxMin"][0], amt["bboxMin"][1], amt["bboxMin"][2])
    kms.header.maxPos = KMSVector3(amt["bboxMax"][0], amt["bboxMax"][1], amt["bboxMax"][2])
    kms.header.pos = KMSVector3(amt.location.x, amt.location.y, amt.location.z)
    
    bones = amt.data.bones
    
    for obj in collection.all_objects:
        if obj.type != "MESH":
            continue
        print("Exporting", obj.name)
        # For now, let's assume direct re-export (so meshes and bones are still tightly linked, not suitable for distribution)
        #kms.header.numMesh += 1
        #kms.header.numBones += 1
        kmsMesh = KMSMesh()
        kmsMesh.flag = obj['flag'] if 'flag' in obj else 1

        kmsMesh.pos.x = obj.location.x
        kmsMesh.pos.y = obj.location.y
        kmsMesh.pos.z = obj.location.z
        kmsMesh.minPos.x = obj.bound_box[0][0]
        kmsMesh.minPos.y = obj.bound_box[0][1]
        kmsMesh.minPos.z = obj.bound_box[0][2]
        kmsMesh.maxPos.x = obj.bound_box[6][0]
        kmsMesh.maxPos.y = obj.bound_box[6][1]
        kmsMesh.maxPos.z = obj.bound_box[6][2]

        bone = bones["bone" + obj.name.split('Mesh')[1]]
        kmsMesh.parentInd = -1
        if bone.parent:
            kmsMesh.parentInd = int(bone.parent.name[4:])
            kmsMesh.parent = kms.meshes[kmsMesh.parentInd]
        # Recursively fix position
        curMesh = kmsMesh.parent
        while curMesh:
            kmsMesh.pos.x -= curMesh.pos.x
            kmsMesh.pos.y -= curMesh.pos.y
            kmsMesh.pos.z -= curMesh.pos.z
            curMesh = curMesh.parent
            
        
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
            
            nodes = mat.node_tree.nodes
            if nodes.get("g_ColorMap") is not None:
                vertexGroup.colorMap = int(nodes["g_ColorMap"].image.name.split('.')[0])
            elif mat.get("colorMapFallback") is not None:
                vertexGroup.colorMap = mat["colorMapFallback"]

            if nodes.get("g_SpecularMap") is not None:
                vertexGroup.specularMap = int(nodes["g_SpecularMap"].image.name.split('.')[0])
            elif mat.get("specularMapFallback") is not None:
                vertexGroup.specularMap = mat["specularMapFallback"]

            if nodes.get("g_EnvironmentMap") is not None:
                vertexGroup.environmentMap = int(nodes["g_EnvironmentMap"].image.name.split('.')[0])
            elif mat.get("environmentMapFallback") is not None:
                vertexGroup.environmentMap = mat["environmentMapFallback"]

            if len(obj.data.uv_layers) > 0:
                vertexGroup.uvs = []
            if len(obj.data.uv_layers) > 1:
                vertexGroup.uvs2 = []
            if len(obj.data.uv_layers) > 2:
                vertexGroup.uvs3 = []
                
            kmsMesh.vertexGroups.append(vertexGroup)
        
        allVertsWritten: List[List[int]] = [[] for _ in range(len(kmsMesh.vertexGroups))]
        flip = False
        for polygon in obj.data.polygons:
            assert(polygon.loop_total == 3) # Not triangulated!
            polyMat = polygon.material_index
            vertexGroup = kmsMesh.vertexGroups[polyMat]
            vertsWritten = allVertsWritten[polyMat]
            loopIndices = list(range(polygon.loop_start, polygon.loop_start + 3))
            loopIndices = [loopIndices[0], loopIndices[2], loopIndices[1]]
            vertexIndices = [obj.data.loops[i].vertex_index for i in loopIndices]
            if flip:
                other_check_index = 1
                compress_add_index = 2
            else:
                other_check_index = 2
                compress_add_index = 1
            if len(vertsWritten) > 0 and \
               vertexIndices[other_check_index] == vertsWritten[-1] and \
               vertexIndices[0] == vertsWritten[-2]:
                # Optimize, baby!
                vertsWritten += [vertexIndices[compress_add_index]]
                vert3 = obj.data.vertices[vertexIndices[compress_add_index]]
                vertexGroup.vertices += [KMSVertex(round(vert3.co.x), round(vert3.co.y), round(vert3.co.z), \
                                                   getVertWeight(vert3))]
                vertexGroup.normals += [KMSNormal(vert3.normal.x * -4096, vert3.normal.y * -4096, vert3.normal.z * -4096, True)]
                if len(obj.data.uv_layers) > 0:
                    vertexGroup.uvs += [kmsUvFromLayerAndLoop(obj, 0, loopIndices[compress_add_index])]
                if len(obj.data.uv_layers) > 1:
                    vertexGroup.uvs2 += [kmsUvFromLayerAndLoop(obj, 1, loopIndices[compress_add_index])]
                if len(obj.data.uv_layers) > 2:
                    vertexGroup.uvs3 += [kmsUvFromLayerAndLoop(obj, 2, loopIndices[compress_add_index])]
                flip = not flip
            else:
                # add all three :(
                vertsWritten += vertexIndices
                vert1 = obj.data.vertices[vertexIndices[0]]
                vert2 = obj.data.vertices[vertexIndices[1]]
                vert3 = obj.data.vertices[vertexIndices[2]]
                vertexGroup.vertices += [
                    KMSVertex(round(vert1.co.x), round(vert1.co.y), round(vert1.co.z), getVertWeight(vert1)),
                    KMSVertex(round(vert2.co.x), round(vert2.co.y), round(vert2.co.z), getVertWeight(vert2)),
                    KMSVertex(round(vert3.co.x), round(vert3.co.y), round(vert3.co.z), getVertWeight(vert3))
                ]
                vertexGroup.normals += [
                    KMSNormal(vert1.normal.x * -4096, vert1.normal.y * -4096, vert1.normal.z * -4096, False),
                    KMSNormal(vert2.normal.x * -4096, vert2.normal.y * -4096, vert2.normal.z * -4096, False),
                    KMSNormal(vert3.normal.x * -4096, vert3.normal.y * -4096, vert3.normal.z * -4096, True)
                ]
                if len(obj.data.uv_layers) > 0:
                    vertexGroup.uvs += [
                        kmsUvFromLayerAndLoop(obj, 0, loopIndices[0]),
                        kmsUvFromLayerAndLoop(obj, 0, loopIndices[1]),
                        kmsUvFromLayerAndLoop(obj, 0, loopIndices[2])
                    ]
                if len(obj.data.uv_layers) > 1:
                    vertexGroup.uvs2 += [
                        kmsUvFromLayerAndLoop(obj, 1, loopIndices[0]),
                        kmsUvFromLayerAndLoop(obj, 1, loopIndices[1]),
                        kmsUvFromLayerAndLoop(obj, 1, loopIndices[2])
                    ]
                if len(obj.data.uv_layers) > 2:
                    vertexGroup.uvs3 += [
                        kmsUvFromLayerAndLoop(obj, 2, loopIndices[0]),
                        kmsUvFromLayerAndLoop(obj, 2, loopIndices[1]),
                        kmsUvFromLayerAndLoop(obj, 2, loopIndices[2])
                    ]
                flip = False
        
        obj['kmsVertSideChannel'] = sum(allVertsWritten, []) # flatten
        kms.meshes.append(kmsMesh)
    
    with open(kms_file, "wb") as f:
        kms.writeToFile(f)
    return {'FINISHED'}
