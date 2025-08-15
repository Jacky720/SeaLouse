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
    kms.header.minPos = KMSVector3().set(amt["bboxMin"])
    kms.header.maxPos = KMSVector3().set(amt["bboxMax"])
    kms.header.pos = KMSVector3().set(amt.location)
    
    bones = amt.data.bones
    forceBoneCount = len(bones)
    
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
                vertexGroup.vertices += [kmsVertFromVert(mesh.vertices[vert]) for vert in vertexIndices]
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
    
    with open(kms_file, "wb") as f:
        kms.writeToFile(f, forceBoneCount=forceBoneCount)
    return {'FINISHED'}
