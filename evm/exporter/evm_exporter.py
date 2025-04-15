import bpy
from ..evm import *
import os
from mathutils import Vector

def evmUvFromLayerAndLoop(obj, uvLayer: int, loopIndex: int) -> EVMUv:
    uv = obj.data.uv_layers[uvLayer].uv[loopIndex].vector
    return EVMUv(uv.x * 4096, (1 - uv.y) * 4096)

def getVertWeight(vert) -> int:
    if vert.groups[0].group == 0: # weight is correct
        return int(vert.groups[0].weight * 4096)
    if len(vert.groups) == 2: # weights are in wrong order (may be impossible, handle anyway)
        return int(vert.groups[1].weight * 4096)
    return 0 # vertex is only weighted to parent

def main(evm_file: str, collection_name: str):
    evm = EVM()
    
    collection = bpy.data.collections[collection_name]
    
    amt = [x for x in collection.all_objects if x.type == "ARMATURE"][0]
    evm.header.evmType = amt["evmType"]
    evm.header.strcode = amt["strcode"]
    evm.header.minPos = EVMVector3(amt["bboxMin"][0], amt["bboxMin"][1], amt["bboxMin"][2])
    evm.header.maxPos = EVMVector3(amt["bboxMax"][0], amt["bboxMax"][1], amt["bboxMax"][2])
    
    bones = amt.data.bones
    
    for obj in collection.all_objects:
        if obj.type != "MESH":
            continue
        print("Exporting", obj.name)
        # For now, let's assume direct re-export (so meshes and bones are still tightly linked, not suitable for distribution)
        #evm.header.numMesh += 1
        #evm.header.numBones += 1
        evmMesh = EVMMesh()
        evmMesh.flag = 1

        evmMesh.pos.x = obj.location.x
        evmMesh.pos.y = obj.location.y
        evmMesh.pos.z = obj.location.z
        evmMesh.minPos.x = obj.bound_box[0][0]
        evmMesh.minPos.y = obj.bound_box[0][1]
        evmMesh.minPos.z = obj.bound_box[0][2]
        evmMesh.maxPos.x = obj.bound_box[6][0]
        evmMesh.maxPos.y = obj.bound_box[6][1]
        evmMesh.maxPos.z = obj.bound_box[6][2]

        bone = bones["bone" + obj.name.split('Mesh')[1]]
        evmMesh.parentInd = -1
        if bone.parent:
            evmMesh.parentInd = int(bone.parent.name[4:])
            evmMesh.parent = evm.meshes[evmMesh.parentInd]
        # Recursively fix position
        curMesh = evmMesh.parent
        while curMesh:
            evmMesh.pos.x -= curMesh.pos.x
            evmMesh.pos.y -= curMesh.pos.y
            evmMesh.pos.z -= curMesh.pos.z
            curMesh = curMesh.parent
            
        
        # Create vertex groups from materials
        for materialSlot in obj.material_slots:
            #evmMesh.numVertexGroup += 1
            mat = materialSlot.material
            
            vertexGroup = EVMVertexGroup()
            if "flag" in mat:
                vertexGroup.flag = mat["flag"]
            elif obj.name == "evmMesh0":
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
                
            evmMesh.vertexGroups.append(vertexGroup)
        
        allVertsWritten: List[List[int]] = [[] for _ in range(len(evmMesh.vertexGroups))]
        flip = False
        for polygon in obj.data.polygons:
            assert(polygon.loop_total == 3) # Not triangulated!
            polyMat = polygon.material_index
            vertexGroup = evmMesh.vertexGroups[polyMat]
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
                vertexGroup.vertices += [EVMVertex(round(vert3.co.x), round(vert3.co.y), round(vert3.co.z), \
                                                   getVertWeight(vert3))]
                vertexGroup.normals += [EVMNormal(vert3.normal.x * -4096, vert3.normal.y * -4096, vert3.normal.z * -4096, True)]
                if len(obj.data.uv_layers) > 0:
                    vertexGroup.uvs += [evmUvFromLayerAndLoop(obj, 0, loopIndices[compress_add_index])]
                if len(obj.data.uv_layers) > 1:
                    vertexGroup.uvs2 += [evmUvFromLayerAndLoop(obj, 1, loopIndices[compress_add_index])]
                if len(obj.data.uv_layers) > 2:
                    vertexGroup.uvs3 += [evmUvFromLayerAndLoop(obj, 2, loopIndices[compress_add_index])]
                flip = not flip
            else:
                # add all three :(
                vertsWritten += vertexIndices
                vert1 = obj.data.vertices[vertexIndices[0]]
                vert2 = obj.data.vertices[vertexIndices[1]]
                vert3 = obj.data.vertices[vertexIndices[2]]
                vertexGroup.vertices += [
                    EVMVertex(round(vert1.co.x), round(vert1.co.y), round(vert1.co.z), getVertWeight(vert1)),
                    EVMVertex(round(vert2.co.x), round(vert2.co.y), round(vert2.co.z), getVertWeight(vert2)),
                    EVMVertex(round(vert3.co.x), round(vert3.co.y), round(vert3.co.z), getVertWeight(vert3))
                ]
                vertexGroup.normals += [
                    EVMNormal(vert1.normal.x * -4096, vert1.normal.y * -4096, vert1.normal.z * -4096, False),
                    EVMNormal(vert2.normal.x * -4096, vert2.normal.y * -4096, vert2.normal.z * -4096, False),
                    EVMNormal(vert3.normal.x * -4096, vert3.normal.y * -4096, vert3.normal.z * -4096, True)
                ]
                if len(obj.data.uv_layers) > 0:
                    vertexGroup.uvs += [
                        evmUvFromLayerAndLoop(obj, 0, loopIndices[0]),
                        evmUvFromLayerAndLoop(obj, 0, loopIndices[1]),
                        evmUvFromLayerAndLoop(obj, 0, loopIndices[2])
                    ]
                if len(obj.data.uv_layers) > 1:
                    vertexGroup.uvs2 += [
                        evmUvFromLayerAndLoop(obj, 1, loopIndices[0]),
                        evmUvFromLayerAndLoop(obj, 1, loopIndices[1]),
                        evmUvFromLayerAndLoop(obj, 1, loopIndices[2])
                    ]
                if len(obj.data.uv_layers) > 2:
                    vertexGroup.uvs3 += [
                        evmUvFromLayerAndLoop(obj, 2, loopIndices[0]),
                        evmUvFromLayerAndLoop(obj, 2, loopIndices[1]),
                        evmUvFromLayerAndLoop(obj, 2, loopIndices[2])
                    ]
                flip = False
        
        obj['evmVertSideChannel'] = sum(allVertsWritten, []) # flatten
        evm.meshes.append(evmMesh)
    
    with open(evm_file, "wb") as f:
        evm.writeToFile(f)
    return {'FINISHED'}
