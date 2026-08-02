import bpy
from ..cmdl import *
from ...util.util import getBoneIndex, getFingerIndex, getVertWeight, getBoneName, getRawNormal, computeStableVertices
import os
import struct
from mathutils import Vector


def setModeSafe(obj, mode):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    with bpy.context.temp_override(active_object=obj, selected_objects=[obj], object=obj):
        bpy.ops.object.mode_set(mode=mode)


def refreshMeshState(obj):
    setModeSafe(obj, 'EDIT')
    setModeSafe(obj, 'OBJECT')


def quantizeNormalComponents(x, y, z, renormalize=True):
    if renormalize:
        total = (x*x + y*y + z*z) ** 0.5
        if total != 0.0:
            x, y, z = x / total, y / total, z / total
    # int() matches c++ uint32 cast, truncating instead of rounding.
    nx = int(x * float((1 << 10) - 1))
    ny = int(y * float((1 << 10) - 1))
    nz = int(z * float((1 << 9) - 1))
    return nx, ny, nz

def quantizeUvForWeld(u, v):
    return struct.pack("<ee", u, v)

def evmWeightKey(mesh, fingerIndex):
    def key(vertex):
        return tuple(sorted(
            (getBoneIndex(mesh.vertex_groups[g.group].name, fingerIndex), round(g.weight, 6))
            for g in vertex.groups if g.weight > 0
        ))
    return key

def kmsWeightKey(mesh, bone):
    def key(vertex):
        return (round(getVertWeight(vertex, mesh, bone.name), 6),)
    return key

def weldGroupKey(mesh, loop, numUvLayers, weightKeyFn):
    vertex = mesh.data.vertices[loop.vertex_index]
    return (
        round(vertex.co.x, 4), round(vertex.co.y, 4), round(vertex.co.z, 4),
        tuple(
            quantizeUvForWeld(
                mesh.data.uv_layers[k].uv[loop.index].vector.x,
                1 - mesh.data.uv_layers[k].uv[loop.index].vector.y,
            )
            for k in range(numUvLayers)
        ),
        weightKeyFn(vertex),
    )

def uvLayerIsNull(mesh, layerIndex, nullUv):
    if len(mesh.data.uv_layers) <= layerIndex:
        return True
    layer = mesh.data.uv_layers[layerIndex]
    return all((round(item.vector.x, 4), round(item.vector.y, 4)) == nullUv for item in layer.uv)

def buildWeldedMesh(mesh, weightKeyFn, stableVertices, normalizeNormal):
    numUvLayers = len(mesh.data.uv_layers)
    material_lists = [[] for _ in range(len(mesh.material_slots))]
    material_seen = [dict() for _ in range(len(mesh.material_slots))]  # groupKey -> {(nx,ny,nz): localIdx}
    loop_to_local = {}  # loop.index -> (material_index, local_index_within_material)
    for polygon in mesh.data.polygons:
        matIdx = polygon.material_index
        loops = material_lists[matIdx]
        seen = material_seen[matIdx]
        for loopIndex in polygon.loop_indices:
            loop = mesh.data.loops[loopIndex]
            gkey = weldGroupKey(mesh, loop, numUvLayers, weightKeyFn)
            nrm = getRawNormal(mesh.data, loop.vertex_index, loop.normal, stableVertices)
            nxyz = quantizeNormalComponents(-nrm.x, -nrm.y, -nrm.z, normalizeNormal)
            normalBuckets = seen.setdefault(gkey, {})
            localIdx = normalBuckets.get(nxyz)
            # loops within 1 unit in packed space count as the same normal, but skip a real (0,0,0)
            # (glass materials have those, don't want it merged into a nearby bucket)
            if localIdx is None and nxyz != (0, 0, 0):
                nx, ny, nz = nxyz
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        for dz in (-1, 0, 1):
                            localIdx = normalBuckets.get((nx + dx, ny + dy, nz + dz))
                            if localIdx is not None:
                                break
                        if localIdx is not None:
                            break
                    if localIdx is not None:
                        break
            if localIdx is None:
                localIdx = len(loops)
                loops.append(loop)
            normalBuckets.setdefault(nxyz, localIdx)
            loop_to_local[loopIndex] = (matIdx, localIdx)
    return material_lists, loop_to_local


def main(cmdl_file: str, collection_name: str, evmMode: bool = False, bigMode: bool = False):

    cmdl = CMDL()
    
    collection = bpy.data.collections[collection_name]
    
    amt = [x for x in collection.all_objects if x.type == "ARMATURE"][0]
    bones = amt.data.bones
    meshes = [x for x in collection.all_objects if x.type == "MESH"]


    fingerIndex = getFingerIndex([bone.name for bone in bones]) if evmMode else -1

    # KMS - renormalize blender's normals back to unit length
    # EVM normals are fine to use raw
    normalizeNormal = not evmMode

    meshBones = {}
    weldedByMesh = {}
    stableVerticesByMesh = {}
    for mesh in meshes:
        refreshMeshState(mesh)
        if bpy.app.version < (4, 1):
            mesh.data.calc_normals_split()
        stableVerticesByMesh[mesh.name] = computeStableVertices(mesh.data)
        if evmMode:
            weightKeyFn = evmWeightKey(mesh, fingerIndex)
        else:
            meshIndex = int(mesh.name.split('Mesh')[1])
            bone = bones.get(getBoneName(meshIndex)) or bones[meshIndex]
            meshBones[mesh.name] = bone
            weightKeyFn = kmsWeightKey(mesh, bone)
        weldedByMesh[mesh.name] = buildWeldedMesh(mesh, weightKeyFn, stableVerticesByMesh[mesh.name], normalizeNormal)

    # Vertex positions and normals
    print("Computing coordinates")
    posSection = CMDLSection(b"POS0")
    nrmSection = CMDLSection(b"NRM0")
    nrmSection.data.renormalize = normalizeNormal

    for mesh in meshes:
        material_lists, _ = weldedByMesh[mesh.name]
        meshmesh = mesh.data
        bone = None if evmMode else meshBones[mesh.name]
        for matLoops in material_lists:
            for loop in matLoops:
                vertex = meshmesh.vertices[loop.vertex_index]
                w = 1.0 if evmMode else getVertWeight(vertex, mesh, bone.name)
                posSection.data.data.append((vertex.co.x, vertex.co.y, vertex.co.z, w))
                nrm = getRawNormal(meshmesh, loop.vertex_index, loop.normal, stableVerticesByMesh[mesh.name])
                nrmSection.data.data.append((-nrm.x, -nrm.y, -nrm.z))

    cmdl.sections.append(posSection)
    cmdl.sections.append(nrmSection)

    # UV Maps
    print("Computing UV maps")
    nullUv = (0.0, 1.0) if evmMode else (0.0, 0.0)
    uv_sections: List[CMDLSectionData] = []
    # maps uv layer index -> its actual section slot, skipping layers that are null on every mesh
    # (dummy/trigger volumes etc) instead of writing an all-default TEX section for nothing
    uv_section_for_layer = {}
    for layerIdx, tag in enumerate((b"TEX0", b"TEX1", b"TEX2")):
        if any(len(mesh.data.uv_layers) > layerIdx and not uvLayerIsNull(mesh, layerIdx, nullUv) for mesh in meshes):
            uv_section_for_layer[layerIdx] = len(uv_sections)
            uv_sections.append(CMDLSection(tag))

    for mesh in meshes:
        material_lists, _ = weldedByMesh[mesh.name]
        # UVs are attached to loops, not vertices, making this part more complex
        for matLoops in material_lists:
            for loop in matLoops:
                for layerIdx, sectionIdx in uv_section_for_layer.items():
                    if len(mesh.data.uv_layers) > layerIdx:
                        uv = mesh.data.uv_layers[layerIdx].uv[loop.index].vector
                        uv_sections[sectionIdx].data.data.append((uv.x, 1 - uv.y))
                    else:
                        uv_sections[sectionIdx].data.data.append((0, 0))

    cmdl.sections += uv_sections

    # EVM only- bone weights
    allSkinningTables = {}
    if evmMode:
        print("Computing bone weights")
        boniSection = CMDLSection(b"BONI")
        bonwSection = CMDLSection(b"BONW")

        for mesh in meshes:
            material_lists, _ = weldedByMesh[mesh.name]
            skinningTables = [[] for _ in range(len(mesh.material_slots))]
            allSkinningTables[mesh.name] = skinningTables
            for matIdx, matLoops in enumerate(material_lists):
                skinningTable = skinningTables[matIdx]
                for loop in matLoops:
                    vertex = mesh.data.vertices[loop.vertex_index]
                    boneIndices = []
                    boneWeights = []
                    for group in vertex.groups:
                        if group.weight == 0:
                            continue
                        boneIndex = getBoneIndex(mesh.vertex_groups[group.group].name, fingerIndex)
                        if boneIndex in skinningTable:
                            boneIndices.append(skinningTable.index(boneIndex))
                        else:
                            boneIndices.append(len(skinningTable))
                            skinningTable.append(boneIndex)
                        boneWeights.append(group.weight)

                    assert(all([0.0 < x <= 1.0 for x in boneWeights]))
                    weightTotal = sum(boneWeights) # Force normalize
                    for i, weight in enumerate(boneWeights):
                        boneWeights[i] = weight * (1.0 / weightTotal)

                    while len(boneWeights) < 4:
                        boneIndices.append(0)
                        boneWeights.append(0.0)
                    # Sort weights in descending order
                    weightPairs = sorted([(boneIndices[i], boneWeights[i]) for i in range(4)],
                                         key=lambda x: -x[1])
                    boniSection.data.data.append([x[0] for x in weightPairs])
                    bonwSection.data.data.append([x[1] for x in weightPairs])
                    print(weightPairs)

        cmdl.sections.append(boniSection)
        cmdl.sections.append(bonwSection)

    # Original (KMS) indexing
    print("Computing original-file indexes")
    oidxSection = CMDLSection(b"OIDX")

    vertIndexOffset = 0
    for mesh in meshes:
        kmsOidxLookup = list(mesh["kmsVertSideChannel"])
        material_lists, _ = weldedByMesh[mesh.name]
        meshVertCount = sum(len(l) for l in material_lists)
        for matLoops in material_lists:
            for loop in matLoops:
                vidx = loop.vertex_index
                if vidx not in kmsOidxLookup:
                    print(mesh.name, kmsOidxLookup)
                oidxSection.data.data.append(kmsOidxLookup.index(vidx) + vertIndexOffset)
        vertIndexOffset += meshVertCount

    cmdl.sections.append(oidxSection)
    
    # Tail
    print("Computing mesh list")
    
    vertIndexOffset = 0

    for i, mesh in enumerate(meshes):
        cmdl.tail.numMeshes += len(mesh.material_slots)
        newMeshes = [CMDLMesh() for _ in range(len(mesh.material_slots))]

        material_lists, loop_to_local = weldedByMesh[mesh.name]
        skinningTables = allSkinningTables.get(mesh.name)

        materialBase = []
        base = vertIndexOffset
        for matLoops in material_lists:
            materialBase.append(base)
            base += len(matLoops)
        meshVertCount = base - vertIndexOffset

        startFaceIdx = [-1] * len(mesh.material_slots)
        faceCounts = [0] * len(mesh.material_slots)
        # group by material before writing - each submesh needs its faces contiguous, and editing (deleting faces, joining stuff) scrambles mesh.data.polygons' order
        polygonsByMaterial = [[] for _ in range(len(mesh.material_slots))]
        for polygon in mesh.data.polygons:
            polygonsByMaterial[polygon.material_index].append(polygon)

        seenDegenerateTris = [set() for _ in range(len(mesh.material_slots))]
        for storeIndex, polys in enumerate(polygonsByMaterial):
            if not polys:
                continue
            startFaceIdx[storeIndex] = len(cmdl.tail.faces) * 3
            for polygon in polys:
                newFace = []
                for loopIndex in polygon.loop_indices:
                    matIdx, localIdx = loop_to_local[loopIndex]
                    newFace.append(materialBase[matIdx] + localIdx)
                posKey = tuple(sorted(
                    tuple(round(v, 4) for v in mesh.data.vertices[mesh.data.loops[li].vertex_index].co)
                    for li in polygon.loop_indices
                ))
                # zero-area filler tris show up as exact duplicate pairs sometimes, only keep one
                isDegenerate = len(set(posKey)) < 3
                if isDegenerate:
                    if posKey in seenDegenerateTris[storeIndex]:
                        continue
                    seenDegenerateTris[storeIndex].add(posKey)
                newFace[1], newFace[2] = newFace[2], newFace[1]
                cmdl.tail.faces.append(newFace)
                faceCounts[storeIndex] += 1

        for j, cmdlMesh in enumerate(newMeshes):
            cmdlMesh.meshIndex = i
            cmdlMesh.subMeshIndex = j
            cmdlMesh.startVertex = materialBase[j]
            cmdlMesh.vertexCount = len(material_lists[j])
            cmdlMesh.startFace = startFaceIdx[j]
            cmdlMesh.faceCount = faceCounts[j] * 3
            cmdlMesh.minPos.x = mesh.bound_box[0][0]
            cmdlMesh.minPos.y = mesh.bound_box[0][1]
            cmdlMesh.minPos.z = mesh.bound_box[0][2]
            cmdlMesh.maxPos.x = mesh.bound_box[6][0]
            cmdlMesh.maxPos.y = mesh.bound_box[6][1]
            cmdlMesh.maxPos.z = mesh.bound_box[6][2]
            if evmMode:
                skinningTable = skinningTables[j]
                for bone in skinningTable:
                    if bone == 0xff:
                        break
                    cmdlMesh.bones.append(bone)
                cmdlMesh.boneCount = len(cmdlMesh.bones)
                print("Skinning cmdlMesh to bones:", cmdlMesh.bones)

        vertIndexOffset += meshVertCount
        cmdl.tail.meshes += newMeshes
    
    #print(cmdl.tail.numFaces)
    
    with open(cmdl_file, "wb") as f:
        cmdl.writeToFile(f)
    return {'FINISHED'}
