import bpy
from ..evm import *
import os
from mathutils import Vector


def vertCoordCheck(vert1: EVMVertex, vert2: EVMVertex):
    return vert1.x == vert2.x and vert1.y == vert2.y and vert1.z == vert2.z

def cycleThree(x: list[any]):
    x[0], x[1], x[2] = x[1], x[2], x[0]

def reverseFour(x: list[any]):
    x[0], x[1], x[2], x[3] = x[3], x[2], x[1], x[0]

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
        # TODO: actual per-bone calculation here
        mesh = [x for x in collection.all_objects if x.type == "MESH"][0]
        evmBone.minPos.x = mesh.bound_box[0][0]
        evmBone.minPos.y = mesh.bound_box[0][1]
        evmBone.minPos.z = mesh.bound_box[0][2]
        evmBone.maxPos.x = mesh.bound_box[6][0]
        evmBone.maxPos.y = mesh.bound_box[6][1]
        evmBone.maxPos.z = mesh.bound_box[6][2]
    bpy.ops.object.mode_set(mode='OBJECT')
    
    for i, obj in enumerate(collection.all_objects):
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
            else:
                mesh.flag = 760
            
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
            vertexIndices = [obj.data.loops[j].vertex_index for j in loopIndices]
            for vertIndex in vertexIndices:
                vert = obj.data.vertices[vertIndex]
                assert(len(vert.groups) <= 4) # Please Limit Total weights per vertex
                for bone in vert.groups:
                    boneIndex = boneIndexFromVertGroup(bone, obj)
                    if boneIndex not in mesh.skinningTable:
                        mesh.skinningTable[mesh.numSkin] = boneIndex # If this errors, you have too many bones on one material
                        mesh.numSkin += 1
        
        # Join skinning tables where possible
        startJ = 0
        superSkinningTable = set()
        for j, mesh in enumerate(evm.meshes):
            # Take care of the "single-weight" flag
            #if mesh.flag == 760 and mesh.skinningTable.count(255) < 7:
            #    mesh.flag = 72
            
            if len(superSkinningTable.union([x for x in mesh.skinningTable if x != 0xff])) <= 8:
                superSkinningTable = superSkinningTable.union([x for x in mesh.skinningTable if x != 0xff])
            else: # table full
                processedSkinningTable = sorted(list(superSkinningTable))
                while len(processedSkinningTable) < 8:
                    processedSkinningTable.append(255)
                #print("Using processedSkinningTable:", processedSkinningTable, "failed to join with", mesh.skinningTable)
                for k in range(startJ, j):
                    evm.meshes[k].skinningTable = processedSkinningTable
                startJ = j
                superSkinningTable = set([x for x in mesh.skinningTable if x != 0xff])
            mesh.numSkin = 0
        # Last time
        for j in range(startJ, len(evm.meshes)):
            evm.meshes[j].skinningTable.sort()
                
        
        allVertsWritten: List[List[int]] = [[] for _ in range(len(evm.meshes))]
        #allSkinningTables: List[List[int]] = [[] for _ in range(len(evm.meshes))]
        
        flip = False
        for polygon in obj.data.polygons:
            polyMat = polygon.material_index
            vertexGroup = evm.meshes[polyMat]
            vertsWritten = allVertsWritten[polyMat]
            #someSkinningTables = allSkinningTables[polyMat]
            loopIndices = list(range(polygon.loop_start, polygon.loop_start + 3))
            loopIndices = [loopIndices[0], loopIndices[2], loopIndices[1]]
            vertexIndices = [obj.data.loops[j].vertex_index for j in loopIndices]
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
                #someSkinningTables += [vertexGroup.skinningTable]
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
                
                flip = False
                vertsWritten += vertexIndices
                #someSkinningTables += [vertexGroup.skinningTable] * 3
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
        
        # Brute-force block reversed winding
        for i, mesh in enumerate(evm.meshes):
            if i == 0:
                continue
            prevMesh = evm.meshes[i - 1]
            j = len(prevMesh.vertices) - 1
            # not doing a proper reverse iterator tonight
            flip = False
            while prevMesh.vertices[j].isFace:
                flip = not flip
                j -= 1
            if not flip:
                print("Mesh %d does NOT end with a flip" % (i - 1))
                continue
            # Alright, the final check
            elif (vertCoordCheck(prevMesh.vertices[-2], mesh.vertices[0]) and
                  vertCoordCheck(prevMesh.vertices[-1], mesh.vertices[1])):
                # Okay, as we have it here, the game is gonna screw us over.
                # We need a way to reshuffle the vertices* such that that doesn't happen
                # *and normals, weights, and UVs
                print("Inverted face detected on mesh %d!" % i)
                # 3 verts: change 012 to 120
                # 4 verts: change 0123 (012, 321) to 3210 (321, 012)
                # 5+ verts: change 01234 (012, 321, 234) to 3210234 (321, 012, 234)
                # TODO: even if this works, it needs to modify allVertsWritten
                if not mesh.vertices[3].isFace: # 3 verts
                    cycleThree(mesh.vertices)
                    mesh.vertices[1].isFace = False
                    mesh.vertices[2].isFace = True
                    cycleThree(mesh.normals)
                    cycleThree(mesh.weights)
                    if mesh.uvs is not None:
                        cycleThree(mesh.uvs)
                    if mesh.uvs2 is not None:
                        cycleThree(mesh.uvs2)
                    if mesh.uvs3 is not None:
                        cycleThree(mesh.uvs3)
                else: # 4+ verts
                    reverseFour(mesh.vertices)
                    # 01[23] -> 32[10]
                    for j in range(4):
                        mesh.vertices[j].isFace = not mesh.vertices[j].isFace
                    reverseFour(mesh.normals)
                    reverseFour(mesh.weights)
                    if mesh.uvs is not None:
                        reverseFour(mesh.uvs)
                    if mesh.uvs2 is not None:
                        reverseFour(mesh.uvs2)
                    if mesh.uvs3 is not None:
                        reverseFour(mesh.uvs3)
                
                if mesh.vertices[4].isFace: # 5+ verts, actual expansion
                    mesh.vertices.insert(4, mesh.vertices[0])
                    mesh.vertices.insert(4, mesh.vertices[1])
                    mesh.normals.insert(4, mesh.normals[0])
                    mesh.normals.insert(4, mesh.normals[1])
                    mesh.weights.insert(4, mesh.weights[0])
                    mesh.weights.insert(4, mesh.weights[1])
                    if mesh.uvs is not None:
                        mesh.uvs.insert(4, mesh.uvs[0])
                        mesh.uvs.insert(4, mesh.uvs[1])
                    if mesh.uvs2 is not None:
                        mesh.uvs2.insert(4, mesh.uvs2[0])
                        mesh.uvs2.insert(4, mesh.uvs2[1])
                    if mesh.uvs3 is not None:
                        mesh.uvs3.insert(4, mesh.uvs3[0])
                        mesh.uvs3.insert(4, mesh.uvs3[1])
                        
        
        obj['kmsVertSideChannel'] = sum(allVertsWritten, []) # flatten
        #obj['evmSkinSideChannel'] = sum(allSkinningTables, [])
    
    with open(evm_file, "wb") as f:
        evm.writeToFile(f)
    return {'FINISHED'}
