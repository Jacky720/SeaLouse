import bpy
from ..cmdl import *
import os
from mathutils import Vector

def getVertWeight(vert) -> float:
    if vert.groups[0].group == 0: # weight is correct
        return vert.groups[0].weight
    if len(vert.groups) == 2 and vert.groups[1].group == 0: # weights are in wrong order (may be impossible, handle anyway)
        return vert.groups[1].weight
    return 0.0 # vertex is only weighted to parent

def main(cmdl_file: str, collection_name: str, evmMode: bool = False):
    cmdl = CMDL()
    
    collection = bpy.data.collections[collection_name]
    
    amt = [x for x in collection.all_objects if x.type == "ARMATURE"][0]
    bones = amt.data.bones
    meshes = [x for x in collection.all_objects if x.type == "MESH"]
    
    # Vertex positions and normals
    posSection = CMDLSection(b"POS0")
    nrmSection = CMDLSection(b"NRM0")

    for mesh in meshes:
        for vertex in mesh.data.vertices:
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
        prevVertexIndex = -1
        # UVs are attached to loops, not vertices, making this part more complex
        for loop in sorted(mesh.data.loops, key=lambda loop: loop.vertex_index):
            if loop.vertex_index == prevVertexIndex:
                continue
            prevVertexIndex = loop.vertex_index
            for i in range(3):
                if len(mesh.data.uv_layers) > i:
                    uv = mesh.data.uv_layers[i].uv[loop.index].vector
                    uv_sections[i].data.data.append((uv.x, 1 - uv.y))
                elif len(uv_sections) > i:
                    uv_sections[i].data.data.append((0, 0))
    
    cmdl.sections += uv_sections
    
    # Original (KMS) indexing
    oidxSection = CMDLSection(b"OIDX")
    
    vertIndexOffset = 0
    for mesh in meshes:
        kmsOidxLookup = list(mesh["kmsVertSideChannel"])
        for i in range(len(mesh.data.vertices)):
            oidxSection.data.data.append(kmsOidxLookup.index(i) + vertIndexOffset)
        vertIndexOffset += len(mesh.data.vertices)
    
    cmdl.sections.append(oidxSection)
    
    # Tail
    
    vertIndexOffset = 0
    faceIndexOffset = 0
    
    for i, mesh in enumerate(meshes):
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
            loops = [mesh.data.loops[k] for k in range(polygon.loop_start, polygon.loop_start + 3)]
            newFace = [loop.vertex_index + vertIndexOffset for loop in loops]
            cmdl.tail.faces.append(newFace)
            # Mesh vertex limits
            for loop in loops:
                vertexIndex = loop.vertex_index
                if minVerts[storeIndex] == -1 or vertexIndex < minVerts[storeIndex]:
                    minVerts[storeIndex] = vertexIndex
                if vertexIndex > maxVerts[storeIndex]:
                    maxVerts[storeIndex] = vertexIndex
        
        for j, cmdlMesh in enumerate(newMeshes):
            cmdlMesh.meshIndex = i
            cmdlMesh.subMeshIndex = j
            cmdlMesh.startVertex = minVerts[j] + vertIndexOffset
            cmdlMesh.vertexCount = maxVerts[j] - minVerts[j] + 1
            cmdlMesh.startFace = (minFaces[j]) * 3 + faceIndexOffset
            cmdlMesh.faceCount = (maxFaces[j] - minFaces[j] + 1) * 3
            cmdlMesh.minPos.x = mesh.bound_box[0][0]
            cmdlMesh.minPos.y = mesh.bound_box[0][1]
            cmdlMesh.minPos.z = mesh.bound_box[0][2]
            cmdlMesh.maxPos.x = mesh.bound_box[6][0]
            cmdlMesh.maxPos.y = mesh.bound_box[6][1]
            cmdlMesh.maxPos.z = mesh.bound_box[6][2]
            #for k in range(cmdlMesh.startVertex, cmdlMesh.startVertex + cmdlMesh.vertexCount):

            #print(cmdlMesh.startFace, cmdlMesh.faceCount)
        
        vertIndexOffset += len(mesh.data.vertices)
        faceIndexOffset += len(mesh.data.polygons) * 3
        
        cmdl.tail.meshes += newMeshes
    
    #print(cmdl.tail.numFaces)
    
    with open(cmdl_file, "wb") as f:
        cmdl.writeToFile(f)
    return {'FINISHED'}
