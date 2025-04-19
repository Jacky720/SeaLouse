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

def boneIndexFromVertGroup(vertexGroup, obj) -> int:
    boneName = obj.vertex_groups[vertexGroup.group].name
    return int(boneName.split("bone")[1])


def main(evm_file: str, collection_name: str):
    evm = EVM()
    
    collection = bpy.data.collections[collection_name]
    
    amt = [x for x in collection.all_objects if x.type == "ARMATURE"][0]
    #evm.header.evmType = amt["evmType"]
    evm.header.strcode = amt["strcode"]
    evm.header.flag = amt["flag"]
    evm.header.minPos = EVMVector3(amt["bboxMin"][0], amt["bboxMin"][1], amt["bboxMin"][2])
    evm.header.maxPos = EVMVector3(amt["bboxMax"][0], amt["bboxMax"][1], amt["bboxMax"][2])
    
    evm.bones = [EVMBone() for _ in range(len(amt.data.bones))]
    
    bpy.ops.object.select_all(action='DESELECT')
    amt.select_set(True)
    bpy.context.view_layer.objects.active = amt
    bpy.ops.object.mode_set(mode='EDIT')
    for bone in amt.data.edit_bones:
        print(bone.name)
        evmBone = evm.bones[int(bone.name.split("bone")[1])]
        evmBone.worldPos.x = bone.head.x
        evmBone.worldPos.y = bone.head.y
        evmBone.worldPos.z = bone.head.z
        evmBone.relativePos.x = bone.head.x
        evmBone.relativePos.y = bone.head.y
        evmBone.relativePos.z = bone.head.z
        if bone.parent:
            evmBone.parentInd = int(bone.parent.name.split("bone")[1])
            evmBone.relativePos.x -= bone.parent.head.x
            evmBone.relativePos.y -= bone.parent.head.y
            evmBone.relativePos.z -= bone.parent.head.z
        # minPos and maxPos?
    bpy.ops.object.mode_set(mode='OBJECT')
    
    for obj in collection.all_objects:
        if obj.type != "MESH":
            continue
        print("Exporting", obj.name)
        # For now, let's assume direct re-export (so meshes and bones are still tightly linked, not suitable for distribution)
        #evm.header.numMesh += 1
        #evm.header.numBones += 1
        
        # Create vertex groups from materials
        for materialSlot in obj.material_slots:
            #evmMesh.numVertexGroup += 1
            mat = materialSlot.material
            mesh = EVMMesh()
            #evmMesh.flag = 1

            if "flag" in mat:
                mesh.flag = mat["flag"]
            elif obj.name == "evmMesh0":
                mesh.flag = 760
            else:
                mesh.flag = 761
            
            nodes = mat.node_tree.nodes
            if nodes.get("g_ColorMap") is not None:
                mesh.colorMap = int(nodes["g_ColorMap"].image.name.split('.')[0])
            elif mat.get("colorMapFallback") is not None:
                mesh.colorMap = mat["colorMapFallback"]

            if nodes.get("g_SpecularMap") is not None:
                mesh.specularMap = int(nodes["g_SpecularMap"].image.name.split('.')[0])
            elif mat.get("specularMapFallback") is not None:
                mesh.specularMap = mat["specularMapFallback"]

            if nodes.get("g_EnvironmentMap") is not None:
                mesh.environmentMap = int(nodes["g_EnvironmentMap"].image.name.split('.')[0])
            elif mat.get("environmentMapFallback") is not None:
                mesh.environmentMap = mat["environmentMapFallback"]

            if len(obj.data.uv_layers) > 0:
                mesh.uvs = []
            if len(obj.data.uv_layers) > 1:
                mesh.uvs2 = []
            if len(obj.data.uv_layers) > 2:
                mesh.uvs3 = []
            
            mesh.weights = []
                
            evm.meshes.append(mesh)
        
        # Skinning tables - intermediate step for weights later
        for polygon in obj.data.polygons:
            assert(polygon.loop_total == 3) # Not triangulated!
            polyMat = polygon.material_index
            mesh = evm.meshes[polyMat]
            loopIndices = list(range(polygon.loop_start, polygon.loop_start + 3))
            vertexIndices = [obj.data.loops[i].vertex_index for i in loopIndices]
            for vertIndex in vertexIndices:
                vert = obj.data.vertices[vertIndex]
                assert(len(vert.groups) <= 4) # Please Limit Total weights per vertex
                for bone in vert.groups:
                    boneIndex = boneIndexFromVertGroup(bone, obj)
                    if boneIndex not in mesh.skinningTable:
                        mesh.skinningTable[mesh.numSkin] = boneIndex # If this errors, you have too many bones on one material
                        mesh.numSkin += 1
        
        # Join skinning tables where possible
        startI = 0
        superSkinningTable = set()
        for i, mesh in enumerate(evm.meshes):
            if len(superSkinningTable.union([x for x in mesh.skinningTable if x != 0xff])) <= 8:
                superSkinningTable = superSkinningTable.union([x for x in mesh.skinningTable if x != 0xff])
            else: # table full
                processedSkinningTable = sorted(list(superSkinningTable))
                while len(processedSkinningTable) < 8:
                    processedSkinningTable.append(255)
                #print("Using processedSkinningTable:", processedSkinningTable, "failed to join with", mesh.skinningTable)
                for j in range(startI, i):
                    evm.meshes[j].skinningTable = processedSkinningTable
                startI = i
                superSkinningTable = set([x for x in mesh.skinningTable if x != 0xff])
            mesh.numSkin = 0
        # Last time
        for j in range(startI, len(evm.meshes)):
            evm.meshes[j].skinningTable.sort()
            
        
        allVertsWritten: List[List[int]] = [[] for _ in range(len(evm.meshes))]
        allSkinningTables: List[List[int]] = [[] for _ in range(len(evm.meshes))]
        flip = False
        for polygon in obj.data.polygons:
            polyMat = polygon.material_index
            vertexGroup = evm.meshes[polyMat]
            vertsWritten = allVertsWritten[polyMat]
            someSkinningTables = allSkinningTables[polyMat]
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
                someSkinningTables += [vertexGroup.skinningTable]
                vert3 = obj.data.vertices[vertexIndices[compress_add_index]]
                vertexGroup.vertices += [EVMVertex(round(vert3.co.x), round(vert3.co.y), round(vert3.co.z), \
                                                   True)]
                vertexGroup.normals += [EVMNormal(vert3.normal.x * -4096, vert3.normal.y * -4096, vert3.normal.z * -4096)]
                if len(obj.data.uv_layers) > 0:
                    vertexGroup.uvs += [evmUvFromLayerAndLoop(obj, 0, loopIndices[compress_add_index])]
                if len(obj.data.uv_layers) > 1:
                    vertexGroup.uvs2 += [evmUvFromLayerAndLoop(obj, 1, loopIndices[compress_add_index])]
                if len(obj.data.uv_layers) > 2:
                    vertexGroup.uvs3 += [evmUvFromLayerAndLoop(obj, 2, loopIndices[compress_add_index])]
                vertexGroup.weights += [EVMWeights(
                                        [int(x.weight*128) for x in vert3.groups],
                                        [vertexGroup.skinningTable.index(boneIndexFromVertGroup(x, obj)) << 2 for x in vert3.groups])]
                if len(vert3.groups) > vertexGroup.numSkin:
                    vertexGroup.numSkin = len(vert3.groups)
                flip = not flip
            else:
                # add all three :(
                vertsWritten += vertexIndices
                someSkinningTables += [vertexGroup.skinningTable] * 3
                vert1 = obj.data.vertices[vertexIndices[0]]
                vert2 = obj.data.vertices[vertexIndices[1]]
                vert3 = obj.data.vertices[vertexIndices[2]]
                vertexGroup.vertices += [
                    EVMVertex(round(vert1.co.x), round(vert1.co.y), round(vert1.co.z), False),
                    EVMVertex(round(vert2.co.x), round(vert2.co.y), round(vert2.co.z), False),
                    EVMVertex(round(vert3.co.x), round(vert3.co.y), round(vert3.co.z), True)
                ]
                vertexGroup.normals += [
                    EVMNormal(vert1.normal.x * -4096, vert1.normal.y * -4096, vert1.normal.z * -4096),
                    EVMNormal(vert2.normal.x * -4096, vert2.normal.y * -4096, vert2.normal.z * -4096),
                    EVMNormal(vert3.normal.x * -4096, vert3.normal.y * -4096, vert3.normal.z * -4096)
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
                vertexGroup.weights += [EVMWeights(
                                        [int(x.weight*128) for x in vert1.groups],
                                        [vertexGroup.skinningTable.index(boneIndexFromVertGroup(x, obj)) << 2 for x in vert1.groups]),
                                        EVMWeights(
                                        [int(x.weight*128) for x in vert2.groups],
                                        [vertexGroup.skinningTable.index(boneIndexFromVertGroup(x, obj)) << 2 for x in vert2.groups]),
                                        EVMWeights(
                                        [int(x.weight*128) for x in vert3.groups],
                                        [vertexGroup.skinningTable.index(boneIndexFromVertGroup(x, obj)) << 2 for x in vert3.groups])]
                if len(vert1.groups) > vertexGroup.numSkin:
                    vertexGroup.numSkin = len(vert1.groups)
                if len(vert2.groups) > vertexGroup.numSkin:
                    vertexGroup.numSkin = len(vert2.groups)
                if len(vert3.groups) > vertexGroup.numSkin:
                    vertexGroup.numSkin = len(vert3.groups)
                flip = False
        
        obj['kmsVertSideChannel'] = sum(allVertsWritten, []) # flatten
        obj['evmSkinSideChannel'] = sum(allSkinningTables, [])
    
    with open(evm_file, "wb") as f:
        evm.writeToFile(f)
    return {'FINISHED'}
