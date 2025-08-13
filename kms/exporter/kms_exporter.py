import bpy
from ..kms import *
from ...util.util import getBoneName, getBoneIndex
from ...util.util import getVertWeight as rawVertWeight
import os
from mathutils import Vector

def getVertWeight(vert) -> int:
    return int(rawVertWeight(vert) * 4096)

def kmsVertFromVert(vert) -> KMSVertex:
    return KMSVertex(round(vert.co.x), round(vert.co.y), round(vert.co.z), getVertWeight(vert))

def kmsNormFromLoop(loop, isFace: bool) -> KMSNormal:
    return KMSNormal(loop.normal.x * -4096, loop.normal.y * -4096, loop.normal.z * -4096, isFace)

def kmsUvFromLayerAndLoop(mesh, uvLayer: int, loopIndex: int) -> KMSUv:
    uv = mesh.uv_layers[uvLayer].uv[loopIndex].vector
    return KMSUv(uv.x * 4096, (1 - uv.y) * 4096)


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
        # For now, let's assume direct re-export (so meshes and bones are still tightly linked)
        #kms.header.numMesh += 1
        #kms.header.numBones += 1
        mesh = obj.data
        if bpy.app.version < (4, 1):
            mesh.calc_normals_split()
        
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

        bone = bones[getBoneName(int(obj.name.split('Mesh')[1]))]
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

            if len(mesh.uv_layers) > 0:
                vertexGroup.uvs = []
            if len(mesh.uv_layers) > 1:
                vertexGroup.uvs2 = []
            if len(mesh.uv_layers) > 2:
                vertexGroup.uvs3 = []
                
            kmsMesh.vertexGroups.append(vertexGroup)
        
        allVertsWritten: List[List[int]] = [[] for _ in range(len(kmsMesh.vertexGroups))]
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
                # Optimize, baby!
                vertsWritten += [vertexIndices[compress_add_index]]
                vertexGroup.vertices += [kmsVertFromVert(mesh.vertices[vertexIndices[compress_add_index]])]
                vertexGroup.normals += [kmsNormFromLoop(mesh.loops[loopIndices[compress_add_index]], True)]
                if len(mesh.uv_layers) > 0:
                    vertexGroup.uvs += [kmsUvFromLayerAndLoop(mesh, 0, loopIndices[compress_add_index])]
                if len(mesh.uv_layers) > 1:
                    vertexGroup.uvs2 += [kmsUvFromLayerAndLoop(mesh, 1, loopIndices[compress_add_index])]
                if len(mesh.uv_layers) > 2:
                    vertexGroup.uvs3 += [kmsUvFromLayerAndLoop(mesh, 2, loopIndices[compress_add_index])]
                flip = not flip
            else:
                # add all three :(
                vertsWritten += vertexIndices
                vertexGroup.vertices += [kmsVertFromVert(mesh.vertices[vert]) for vert in vertexIndices]
                vertexGroup.normals += [
                    kmsNormFromLoop(mesh.loops[loopIndices[0]], False),
                    kmsNormFromLoop(mesh.loops[loopIndices[1]], False),
                    kmsNormFromLoop(mesh.loops[loopIndices[2]], True)
                ]
                if len(mesh.uv_layers) > 0:
                    vertexGroup.uvs += [
                        kmsUvFromLayerAndLoop(mesh, 0, loopIndices[0]),
                        kmsUvFromLayerAndLoop(mesh, 0, loopIndices[1]),
                        kmsUvFromLayerAndLoop(mesh, 0, loopIndices[2])
                    ]
                if len(mesh.uv_layers) > 1:
                    vertexGroup.uvs2 += [
                        kmsUvFromLayerAndLoop(mesh, 1, loopIndices[0]),
                        kmsUvFromLayerAndLoop(mesh, 1, loopIndices[1]),
                        kmsUvFromLayerAndLoop(mesh, 1, loopIndices[2])
                    ]
                if len(mesh.uv_layers) > 2:
                    vertexGroup.uvs3 += [
                        kmsUvFromLayerAndLoop(mesh, 2, loopIndices[0]),
                        kmsUvFromLayerAndLoop(mesh, 2, loopIndices[1]),
                        kmsUvFromLayerAndLoop(mesh, 2, loopIndices[2])
                    ]
                flip = False
        
        obj['kmsVertSideChannel'] = sum(allVertsWritten, []) # flatten
        kms.meshes.append(kmsMesh)
    
    with open(kms_file, "wb") as f:
        kms.writeToFile(f)
    return {'FINISHED'}
