import bpy
from ..kms import *
import os
from mathutils import Vector


def reset_blend():
    #bpy.ops.object.mode_set(mode='OBJECT')
    for collection in bpy.data.collections:
        for obj in collection.objects:
            collection.objects.unlink(obj)
        bpy.data.collections.remove(collection)
    for bpy_data_iter in (bpy.data.objects, bpy.data.meshes, bpy.data.lights, bpy.data.cameras, bpy.data.libraries):
        for id_data in bpy_data_iter:
            bpy_data_iter.remove(id_data)
    for material in bpy.data.materials:
        bpy.data.materials.remove(material)
    for amt in bpy.data.armatures:
        bpy.data.armatures.remove(amt)
    for obj in bpy.data.objects:
        bpy.data.objects.remove(obj)
        obj.user_clear()


def construct_mesh(mesh: KMSMesh, kmsCollection, meshInd: int, meshPos):
    vertices = []
    faces = []
    for vertexGroup in mesh.vertexGroups:
        faceIndexOffset = len(vertices)
        vertices += [(vert.x, vert.y, vert.z) for vert in vertexGroup.vertices]
        flip = False
        for i in range(vertexGroup.numVertex):
            if vertexGroup.normals[i].isFace:
                if flip:
                    faces.append((i - 2 + faceIndexOffset, i - 1 + faceIndexOffset, i + faceIndexOffset))
                else:
                    faces.append((i - 2 + faceIndexOffset, i + faceIndexOffset, i - 1 + faceIndexOffset))
                flip = not flip
            else:
                flip = False
    objmesh = bpy.data.meshes.new("kmsMesh%d" % meshInd)
    obj = bpy.data.objects.new(objmesh.name, objmesh)
    obj.location = Vector(meshPos)
    #obj.location = Vector((0,0,0))
    kmsCollection.objects.link(obj)
    objmesh.from_pydata(vertices, [], faces)
    #if normals is not None:
    #    objmesh.normals_split_custom_set_from_vertices(normals)
    objmesh.update(calc_edges=True)


def main(kms_file: str):
    kms = KMS()
    with open(kms_file, "rb") as f:
        kms.fromFile(f)
    
    kmsname = os.path.split(kms_file)[-1] # Split only splits into head and tail, but since we want the last part, we don't need to split the head with kms_file.split(os.sep)

    kmsCollection = bpy.data.collections.get("KMS")
    if not kmsCollection:
        kmsCollection = bpy.data.collections.new("KMS")
        bpy.context.scene.collection.children.link(kmsCollection)

    collection_name = kmsname[:-4]
    if bpy.data.collections.get(collection_name): # oops, duplicate
        collection_suffix = 1
        while True:
            if not bpy.data.collections.get("%s.%03d" % (collection_name, collection_suffix)):
                collection_name += ".%03d" % collection_suffix
                break
            collection_suffix += 1
    col = bpy.data.collections.new(collection_name)
    
    kmsCollection.children.link(col)
    #bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[-1]
    
    for i, mesh in enumerate(kms.meshes):
        meshPos = [mesh.pos.x, mesh.pos.y, mesh.pos.z]
        curMesh = mesh
        while curMesh.parent > -1:
            curMesh = kms.meshes[curMesh.parent]
            meshPos[0] += curMesh.pos.x
            meshPos[1] += curMesh.pos.y
            meshPos[2] += curMesh.pos.z
        construct_mesh(mesh, col, i, tuple(meshPos))
    
    print('Importing finished. ;)')
    return {'FINISHED'}
