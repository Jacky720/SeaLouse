import bpy
from ..cmdl import *
import os
from mathutils import Vector

def getLoops(mesh, bigMode: bool):
    if not bigMode:
        return sorted(mesh.data.loops, key=lambda loop: loop.vertex_index)
    return sum([[mesh.data.loops[y] for y in x.loop_indices] for x in mesh.data.polygons], [])

def getVertices(mesh, bigMode: bool):
    if not bigMode:
        return mesh.data.vertices
    # Seems Blender fucks up the normals whenever I split a mesh apart
    # But it fucks up the UVs when I keep it together
    # Solution: Keep it together, but split the UVs *only in export*
    # Probably skyrockets RAM usage
    return [mesh.data.vertices[x.vertex_index] for x in getLoops(mesh, True)]

def getVertWeight(vert) -> float:
    if vert.groups[0].group == 0: # weight is correct
        return vert.groups[0].weight
    if len(vert.groups) == 2 and vert.groups[1].group == 0: # weights are in wrong order (may be impossible, handle anyway)
        return vert.groups[1].weight
    return 0.0 # vertex is only weighted to parent

# TODO: this and above should probably be from a shared utils file
def boneIndexFromVertGroup(vertexGroup, obj) -> int:
    boneName = obj.vertex_groups[vertexGroup.group].name
    return int(boneName.split("bone")[1])

def main(cmdl_file: str, collection_name: str, evmMode: bool = False, bigMode: bool = False):

    if evmMode:
        bigMode = True # temporary until compressed mode set up for EVM bone skinning

    cmdl = CMDL()
    
    collection = bpy.data.collections[collection_name]
    
    amt = [x for x in collection.all_objects if x.type == "ARMATURE"][0]
    bones = amt.data.bones
    meshes = [x for x in collection.all_objects if x.type == "MESH"]
    
    # Vertex positions and normals
    posSection = CMDLSection(b"POS0")
    nrmSection = CMDLSection(b"NRM0")

    for mesh in meshes:
        for vertex in getVertices(mesh, bigMode):
            if evmMode:
                posSection.data.data.append((vertex.co.x/16, vertex.co.y/16, vertex.co.z/16, 1.0))
            else:
                posSection.data.data.append((vertex.co.x, vertex.co.y, vertex.co.z, getVertWeight(vertex)))
            nrm = vertex.normal
            nrmSection.data.data.append((-nrm.x, -nrm.y, -nrm.z))

    cmdl.sections.append(posSection)
    cmdl.sections.append(nrmSection)
    
    # UV Maps
    uv_sections: List[CMDLSectionData] = []
    if any(len(mesh.data.uv_layers) > 0 for mesh in meshes):
        uv_sections.append(CMDLSection(b"TEX0"))
    if any(len(mesh.data.uv_layers) > 1 for mesh in meshes):
        uv_sections.append(CMDLSection(b"TEX1"))
    if any(len(mesh.data.uv_layers) > 2 for mesh in meshes):
        uv_sections.append(CMDLSection(b"TEX2"))
        
    for mesh in meshes:
        """
        prevMat = -1
        skinningTables = [-1] * len(mesh.material_slots)
        kmsOidxLookup = list(mesh["kmsVertSideChannel"])
        evmSkinLookup = list(mesh["evmSkinSideChannel"])
        for poly in mesh.data.polygons:
            if poly.material_index != prevMat:
                vertex = poly.vertices[0]
                skinningTables[poly.material_index] = list(evmSkinLookup[kmsOidxLookup.index(vertex)])
                prevMat = poly.material_index
        for x in skinningTables:
            print(x)
        """
        prevVertexIndex = -1
        # UVs are attached to loops, not vertices, making this part more complex
        for loop in getLoops(mesh, bigMode):
            if loop.vertex_index == prevVertexIndex and not bigMode:
                continue
            prevVertexIndex = loop.vertex_index
            for i in range(3):
                if len(mesh.data.uv_layers) > i:
                    uv = mesh.data.uv_layers[i].uv[loop.index].vector
                    uv_sections[i].data.data.append((uv.x, 1 - uv.y))
                elif len(uv_sections) > i:
                    uv_sections[i].data.data.append((0, 0))
    
    cmdl.sections += uv_sections
    
    # EVM only- bone weights
    if evmMode:
        boniSection = CMDLSection(b"BONI")
        bonwSection = CMDLSection(b"BONW")
        vertIndexOffset = 0
        for mesh in meshes:
            kmsOidxLookup = list(mesh["kmsVertSideChannel"])
            # TODO: make this work with multiple meshes (heck, test if the rest of it works with multiple meshes)
            skinningTables = [[] for _ in range(len(mesh.material_slots))]
            prevVertexIndex = -1
            for poly in mesh.data.polygons:
              for vertexIndex in poly.vertices: # TODO: yeah this almost certainly will break outside of bigMode, temporary override at top
                vertex = mesh.data.vertices[vertexIndex]
                skinningTable = skinningTables[poly.material_index]
                boneIndices = []
                boneWeights = []
                for group in vertex.groups:
                    if group.weight == 0:
                        continue
                    boneIndex = boneIndexFromVertGroup(group, mesh)
                    if boneIndex in skinningTable:
                        boneIndices.append(skinningTable.index(boneIndex))
                    else:
                        boneIndices.append(len(skinningTable))
                        skinningTable.append(boneIndex)
                    boneWeights.append(group.weight)
                
                weightTotal = sum(boneWeights) # NORMALIZE KILLING PEOPLE
                for i, weight in enumerate(boneWeights):
                    boneWeights[i] = weight * (1.0 / weightTotal)
                
                while len(boneWeights) < 4:
                    boneIndices.append(0)
                    boneWeights.append(0.0)
                boniSection.data.data.append(boneIndices)
                bonwSection.data.data.append(boneWeights)
            vertIndexOffset += len(getVertices(mesh, bigMode))
        
        cmdl.sections.append(boniSection)
        cmdl.sections.append(bonwSection)
    
    # Original (KMS) indexing
    oidxSection = CMDLSection(b"OIDX")
    
    vertIndexOffset = 0
    for mesh in meshes:
        kmsOidxLookup = list(mesh["kmsVertSideChannel"])
        for vertex in getVertices(mesh, bigMode):
            oidxSection.data.data.append(kmsOidxLookup.index(vertex.index) + vertIndexOffset)
        vertIndexOffset += len(getVertices(mesh, bigMode))
    
    cmdl.sections.append(oidxSection)
    
    # Tail
    
    vertIndexOffset = 0
    faceIndexOffset = 0
    
    for i, mesh in enumerate(meshes):
        kmsOidxLookup = list(mesh["kmsVertSideChannel"])
        vertices = getVertices(mesh, bigMode)
        
        cmdl.tail.numMeshes += len(mesh.material_slots)
        newMeshes = [CMDLMesh() for _ in range(len(mesh.material_slots))]

        minVerts = [-1] * len(mesh.material_slots)
        minFaces = [-1] * len(mesh.material_slots)
        maxVerts = [-1] * len(mesh.material_slots)
        maxFaces = [-1] * len(mesh.material_slots)
        for j, polygon in enumerate(mesh.data.polygons):
            storeIndex = polygon.material_index
            if minFaces[storeIndex] == -1:
                minFaces[storeIndex] = j
            maxFaces[storeIndex] = j
            # Faces
            loops = [mesh.data.loops[k] for k in polygon.loop_indices]
            if bigMode:
                newFace = list(range(j * 3 + vertIndexOffset, j * 3 + vertIndexOffset + 3))
            else:
                newFace = [loop.vertex_index + vertIndexOffset for loop in loops]
            cmdl.tail.faces.append(newFace)
            # Mesh vertex limits
            for vertexIndex in newFace:
                if minVerts[storeIndex] == -1 or vertexIndex < minVerts[storeIndex]:
                    minVerts[storeIndex] = vertexIndex
                if vertexIndex > maxVerts[storeIndex]:
                    maxVerts[storeIndex] = vertexIndex
        
        for j, cmdlMesh in enumerate(newMeshes):
            cmdlMesh.meshIndex = i
            cmdlMesh.subMeshIndex = j
            assert(0 <= minVerts[j] < len(vertices))
            assert(0 <= maxVerts[j] < len(vertices))
            assert(0 <= minFaces[j] < len(vertices))
            assert(0 <= maxFaces[j] < len(vertices))
            cmdlMesh.startVertex = minVerts[j]
            cmdlMesh.vertexCount = maxVerts[j] - minVerts[j] + 1
            cmdlMesh.startFace = (minFaces[j]) * 3 + faceIndexOffset
            cmdlMesh.faceCount = (maxFaces[j] - minFaces[j] + 1) * 3
            cmdlMesh.minPos.x = mesh.bound_box[0][0]
            cmdlMesh.minPos.y = mesh.bound_box[0][1]
            cmdlMesh.minPos.z = mesh.bound_box[0][2]
            cmdlMesh.maxPos.x = mesh.bound_box[6][0]
            cmdlMesh.maxPos.y = mesh.bound_box[6][1]
            cmdlMesh.maxPos.z = mesh.bound_box[6][2]
            if evmMode:
                cmdlMesh.minPos.x /= 16
                cmdlMesh.minPos.y /= 16
                cmdlMesh.minPos.z /= 16
                cmdlMesh.maxPos.x /= 16
                cmdlMesh.maxPos.y /= 16
                cmdlMesh.maxPos.z /= 16
                if bigMode:
                    startVertex = vertices[cmdlMesh.startVertex].index
                else:
                    startVertex = cmdlMesh.startVertex
                skinningTable = skinningTables[j]
                for bone in skinningTable:
                    if bone == 0xff:
                        break
                    cmdlMesh.bones.append(bone)
                cmdlMesh.boneCount = len(cmdlMesh.bones)
                print("Skinning cmdlMesh to bones:", cmdlMesh.bones)
            #for k in range(cmdlMesh.startVertex, cmdlMesh.startVertex + cmdlMesh.vertexCount):

            #print(cmdlMesh.startFace, cmdlMesh.faceCount)
        
        vertIndexOffset += len(vertices)
        faceIndexOffset += len(mesh.data.polygons) * 3
        
        cmdl.tail.meshes += newMeshes
    
    #print(cmdl.tail.numFaces)
    
    with open(cmdl_file, "wb") as f:
        cmdl.writeToFile(f)
    return {'FINISHED'}
