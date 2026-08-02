import bpy
from ..kms import *
from ...util.util import getBoneName, getBoneIndex
from ...util.util import getVertWeight as rawVertWeight
from ...util.util import getRawNormal, computeStableVertices
from ...util.materials import TextureSave


def setModeSafe(obj, mode):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    with bpy.context.temp_override(active_object=obj, selected_objects=[obj], object=obj):
        bpy.ops.object.mode_set(mode=mode)


# fixes blender sometimes reporting stale/empty uv+attribute data right after loading a .blend
def refreshMeshState(obj):
    setModeSafe(obj, 'EDIT')
    setModeSafe(obj, 'OBJECT')


class MeshExportHelper:
    obj: bpy.types.Object
    mesh: bpy.types.Mesh
    
    bone_name: str
    def __init__(self, obj: bpy.types.Object, bone_name: str):
        self.obj = obj
        if obj.type != 'MESH':
            raise Exception(f"Invalid object {obj.name} with type {obj.type} passed to MeshExportHelper")
        self.mesh = obj.data
    
        self.bone_name = bone_name
    def getVertWeight(self, vert) -> int:
        return round(rawVertWeight(vert, self.obj, self.bone_name) * 4096)
    
    def kmsVertFromVert(self, vert) -> KMSVertex:
        return KMSVertex(round(vert.co.x), round(vert.co.y), round(vert.co.z), self.getVertWeight(vert))
    
    def kmsVertFromIndex(self, index) -> KMSVertex:
        return self.kmsVertFromVert(self.mesh.vertices[index])

def kmsNormFromLoop(mesh, loop, isFace: bool, stableVertices) -> KMSNormal:
    nrm = getRawNormal(mesh, loop.vertex_index, loop.normal, stableVertices)
    return KMSNormal(nrm.x * -4096, nrm.y * -4096, nrm.z * -4096, isFace)

def kmsUvFromLayerAndLoop(mesh, uvLayer: int, loopIndex: int) -> KMSUv:
    uv = mesh.uv_layers[uvLayer].uv[loopIndex].vector
    return KMSUv(uv.x * 4096, (1 - uv.y) * 4096)


def main(kms_file: str, collection_name: str, ctxr_dir: str = None, ctxr_bak: str = 'never'):
    kms = KMS()
    
    collection = bpy.data.collections[collection_name]
    
    amt = [x for x in collection.all_objects if x.type == "ARMATURE"][0]
    kms.header.kmsType = amt["kmsType"]
    kms.header.strcode = amt["strcode"]
    kms.header.pos = KMSVector3().set(amt.location)
    kms.header.minPos = KMSVector3().set(amt["bboxMin"])
    kms.header.maxPos = KMSVector3().set(amt["bboxMax"])

    worldBoundsMin = None
    worldBoundsMax = None
    
    setModeSafe(amt, 'EDIT')
    bones = amt.data.edit_bones
    forceBoneCount = len(bones)
    
    texSave = TextureSave()
    
    for obj in collection.all_objects:
        if obj.type != "MESH":
            continue
        print("Exporting", obj.name)

        mesh = obj.data
        refreshMeshState(obj)
        if bpy.app.version < (4, 1):
            mesh.calc_normals_split()
        stableVertices = computeStableVertices(mesh)

        kmsMesh = KMSMesh()
        kmsMesh.flag = obj['flag'] if 'flag' in obj else 1
        
        meshIndex = int(obj.name.split('Mesh')[1])

        # mesh above kicked the armature out of edit mode, re-enter it
        setModeSafe(amt, 'EDIT')
        bones = amt.data.edit_bones
        bone = bones.get(getBoneName(meshIndex)) or bones[meshIndex]

        boneName = bone.name
        if bone.name == 'head_2' and len(bones) == 22:
            # Hair doesn't actually get a bone in KMS?
            forceBoneCount = 21
        print(f"Making mesh for bone {bone.name}, pos {tuple(bone.head)}")
        kmsMesh.pos.set(bone.head)


        objLoc = obj.location
        for v in mesh.vertices:
            wx, wy, wz = v.co.x + objLoc.x, v.co.y + objLoc.y, v.co.z + objLoc.z
            if worldBoundsMin is None:
                worldBoundsMin = KMSVector3(wx, wy, wz)
                worldBoundsMax = KMSVector3(wx, wy, wz)
            else:
                worldBoundsMin.x = min(worldBoundsMin.x, wx)
                worldBoundsMin.y = min(worldBoundsMin.y, wy)
                worldBoundsMin.z = min(worldBoundsMin.z, wz)
                worldBoundsMax.x = max(worldBoundsMax.x, wx)
                worldBoundsMax.y = max(worldBoundsMax.y, wy)
                worldBoundsMax.z = max(worldBoundsMax.z, wz)
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
        

        refreshMeshState(obj)

        allVertsWritten: List[List[int]] = [[] for _ in range(len(kmsMesh.vertexGroups))]
        helper = MeshExportHelper(obj, boneName)
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
                vertexGroup.normals += [kmsNormFromLoop(mesh, mesh.loops[loopIndices[compress_add_index]], True, stableVertices)]
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
                    kmsNormFromLoop(mesh, mesh.loops[loopIndices[0]], False, stableVertices),
                    kmsNormFromLoop(mesh, mesh.loops[loopIndices[1]], False, stableVertices),
                    kmsNormFromLoop(mesh, mesh.loops[loopIndices[2]], True, stableVertices)
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

    if worldBoundsMin is not None:
        # min/max against the original box - never shrink it, otherwise we'll break breakable objects (break break break)
        kms.header.minPos = KMSVector3(
            min(worldBoundsMin.x - kms.header.pos.x, kms.header.minPos.x),
            min(worldBoundsMin.y - kms.header.pos.y, kms.header.minPos.y),
            min(worldBoundsMin.z - kms.header.pos.z, kms.header.minPos.z))
        kms.header.maxPos = KMSVector3(
            max(worldBoundsMax.x - kms.header.pos.x, kms.header.maxPos.x),
            max(worldBoundsMax.y - kms.header.pos.y, kms.header.maxPos.y),
            max(worldBoundsMax.z - kms.header.pos.z, kms.header.maxPos.z))

    setModeSafe(amt, 'OBJECT')

    if ctxr_dir:
        print("Saving new CTXRs...")
        texSave.save_textures(ctxr_dir, ctxr_bak)
        print("CTXR COMPLETE :)")
    
    with open(kms_file, "wb") as f:
        kms.writeToFile(f, forceBoneCount=forceBoneCount)
    return {'FINISHED'}
