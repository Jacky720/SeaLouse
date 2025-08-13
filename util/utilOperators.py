import bpy, bmesh
from mathutils import Matrix
from .util import mgrBoneMap

class SimplifyMGRBones(bpy.types.Operator):
    """Remove "boneXXXX" vertex groups of active object"""
    bl_idname = "sealouse.simplifymgrbones"
    bl_label = "Remove unnamed bones"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        active_object = bpy.context.active_object
        assert(active_object.type == "MESH") # Please run this operator on a mesh
        assert(active_object.parent.type == "ARMATURE") # Please run this operator on a rigged mesh
        bpy.ops.object.mode_set(mode='OBJECT')
        vertex_groups = active_object.vertex_groups
        bones = active_object.parent.data.bones
        vertices = active_object.data.vertices
        
        # Identify parents of unnamed bones
        corrected_parents = {}
        for i, vertex_group in enumerate(vertex_groups):
            if not vertex_group.name.startswith("bone"):
                continue
            bone = bones[vertex_group.name]
            assert(bone.parent is not None) # Root bone is unnamed
            if bone.parent.name not in vertex_groups:
                # Create vertex group
                vertex_groups.new(name=bone.parent.name)
            corrected_parents[i] = vertex_groups[bone.parent.name].index
        
        # Add weight to parent groups
        for i, vertex in enumerate(vertices):
            for group in [x for x in vertex.groups if x.group in corrected_parents]:
                weight = group.weight
                parentGroup = vertex_groups[corrected_parents[group.group]]
                parentGroup.add([i], weight, "ADD")
        
        # Delete unnamed group
        groups_to_delete = [vertex_groups[i] for i in corrected_parents]
        for group in groups_to_delete:
            vertex_groups.remove(group)
        

        bpy.ops.object.mode_set(mode='OBJECT')
        return {'FINISHED'}


class MgrToMgsBones(bpy.types.Operator):
    """Rename vertex weights on selected mesh to bone0, bone1, etc"""
    bl_idname = "sealouse.mgrtomgsbones"
    bl_label = "Convert MGR:R bone weights"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        active_object = bpy.context.active_object
        assert(active_object.type == "MESH") # Please run this operator on a mesh

        print("Converting bones on", active_object.name)
        for vertex_group in active_object.vertex_groups:
            print("Converting", vertex_group.name)
            assert(vertex_group.name in mgrBoneMap) # Unsupported bone detected, see log for last bone
            vertex_group.name = mgrBoneMap[vertex_group.name]

        print("Bone name conversion succeeded!")

        return {'FINISHED'}

class SplitByWeightPairs(bpy.types.Operator):
    """Split a mesh into component "kmsMeshX" parts according to vertex weights
       no I will not make this a feature of the exporter"""
    bl_idname = "sealouse.splittokmsmesh"
    bl_label = "Split by bone"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        active_object = bpy.context.active_object
        assert(active_object.type == "MESH") # Please run this operator on a mesh
        
        weight_name_lookup = [x.name for x in active_object.vertex_groups]
        bone_parent_lookup = [-1, 0, 1, 2, 3, 4, 5, 2, 7, 8, 9, 2, 11, 0, 13, 14, 15, 0, 17, 18, 19]
        
        # First pass freebies (creates obj.001 through obj.021)
        bpy.ops.object.mode_set(mode='EDIT')
        for i in range(21):
            bpy.ops.mesh.select_mode(type='VERT')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')
            vertCount = len(active_object.data.vertices)
            #print("total:", vertCount)
            for vert in active_object.data.vertices:
                vert.select = True
                #print([weight_name_lookup[x.group] for x in vert.groups])
                for group in vert.groups:
                    if group.weight == 0.0:
                        continue
                    weight = weight_name_lookup[group.group]
                    #print(weight)
                    if weight != ("bone%d" % i) and weight != ("bone%d" % bone_parent_lookup[i]):
                        vert.select = False
                        vertCount -= 1
                        break
            bpy.ops.object.mode_set(mode='EDIT')
            #print("splitting:", vertCount)
            if vertCount > 0:
                bpy.ops.mesh.separate()
            else:
                print("No verts for kmsMesh%d, you're gonna have a bad time" % i)
        
        # Second pass is more difficult, literally covering edge cases
        # Places where a [1,2] connects a [2,3]
        # These should interpret the [1,2] as just [2] and give it to the [2,3]
        # Thanks to Limit Total, these can be resolved by face iteration (since no connection is more than 1 face long)
        additionalMeshes = []
        for i in range(21):
            bpy.ops.mesh.select_mode(type='FACE')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')
            foundAny = False
            for poly in active_object.data.polygons:
                groups = set()
                for vert in poly.vertices:
                    for group in active_object.data.vertices[vert].groups:
                        if group.weight == 0.0:
                            continue
                        groups.add(int(weight_name_lookup[group.group].split("bone")[1]))
                if max(groups) == i:
                    poly.select = True
                    foundAny = True
            bpy.ops.object.mode_set(mode='EDIT')
            if foundAny:
                bpy.ops.mesh.separate()
                additionalMeshes.append(i)
            else:
                print("No verts for kmsMesh%d, you're gonna have a bad time" % i)
        
        # Let's zero-index all of these
        bpy.ops.object.mode_set(mode='OBJECT')
        ogObjName = active_object.name
        for i in range(21 + len(additionalMeshes)):
            bpy.data.objects[ogObjName + ".%03d" % (i + 1)].name = ogObjName + ".%03d" % i
        
        # We identify the meshes created in the second pass and merge them into the ones from the first pass
        for i, meshNum in enumerate(additionalMeshes):
            # this section written by the fuckin google ai, I mean it's basically just stackoverflow wrt function calls
            bpy.ops.object.select_all(action='DESELECT')
            newObject = bpy.data.objects[ogObjName + ".%03d" % meshNum]
            newObject.select_set(True)
            bpy.data.objects[ogObjName + ".%03d" % (21 + i)].select_set(True)
            bpy.context.view_layer.objects.active = newObject
            
            bpy.ops.object.join()
            print("Joined %s to %s" % (ogObjName + ".%03d" % (21 + i), ogObjName + ".%03d" % meshNum))
        
        bones = active_object.parent.data.bones
        
        # Correct mesh positions, thanks StackOverflow
        for meshNum in range(21):
            obj = bpy.data.objects[ogObjName + ".%03d" % meshNum]
            obj.name = "kmsMesh%d" % meshNum
            d = obj.data
            mw = obj.matrix_world
            origin = bones[meshNum].head_local - obj.location
        
            T = Matrix.Translation(-origin)
            d.transform(T)
            mw.translation = mw @ origin
            print(origin)
        
        return {'FINISHED'}

class MergeToKMS(bpy.types.Operator):
    """Merge a mesh into existing "kmsMeshX" parts according to vertex weights
       no I will not make this a feature of the exporter"""
    bl_idname = "sealouse.mergetokms"
    bl_label = "Merge to KMS"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        active_object = bpy.context.active_object
        assert(active_object.type == "MESH") # Please run this operator on a mesh
        
        assert(False) # Not implemented-- use SplitByWeightPairs
        
        """ # Doesn't work, bmesh is incomplete
        bmsource = bmesh.new()
        bmsource.from_mesh(active_object.data)
        
        weight_name_lookup = [x.name for x in active_object.vertex_groups]
        
        # I've never been a huge fan of nesting break instructions
        def return_face_if_splittable(face, i):
            for vert in face.verts:
                vert2 = active_object.data.vertices[vert.index]
                weights = [weight_name_lookup[x.group] for x in vert2.groups]
                for weight in weights:
                    if weight != ("bone%d" % i) and weight != ("bone%d" % (i - 1)):
                        return []
            return [face]

        for i in range(21):
            if ("bone%d" % i) not in active_object.vertex_groups:
                continue
            bmsource.verts.index_update()
            faces_to_split = []
            for face in bmsource.faces:
                faces_to_split += return_face_if_splittable(face, i)
            bmdest = bmesh.new()
            bmdest.from_mesh(bpy.data.objects["kmsMesh%d" % i].data)
            bmesh.ops.split(bmsource, geom=faces_to_split, dest=bmdest)
            bmdest.to_mesh(bpy.data.objects["kmsMesh%d" % i].data)
            bmsource.to_mesh(active_object.data) # Update weight array on object proper
        """
        
        return {'FINISHED'}


class SealouseObjectMenu(bpy.types.Menu):
    bl_idname = 'OBJECT_MT_sealouse'
    bl_label = 'SeaLouse'
    def draw(self, context):
        self.layout.operator(SimplifyMGRBones.bl_idname, icon='BONE_DATA')
        self.layout.operator(MgrToMgsBones.bl_idname, icon='BONE_DATA')
        self.layout.operator(SplitByWeightPairs.bl_idname, icon='NONE')
        #self.layout.operator(MergeToKMS.bl_idname, icon='NONE')

SLObjectClasses = {
    SimplifyMGRBones,
    MgrToMgsBones,
    SplitByWeightPairs,
    #MergeToKMS,
    SealouseObjectMenu
}