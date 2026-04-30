import bpy
import os
from ...config import kmsConfig
from ...util.util import replaceExt, texture_modes, changeTextureMode, defaultTexturePaths, triNameFromModel
from bpy_extras.io_utils import ImportHelper

class ImportMgsKms(bpy.types.Operator, ImportHelper):
    '''Load an MGS2 KMS File.'''
    bl_idname = "import_scene.kms_data"
    bl_label = "Import KMS Data"
    bl_options = {'PRESET'}
    filename_ext = ".kms"
    filter_glob: bpy.props.StringProperty(default="*.kms", options={'HIDDEN'})

    reset_blend: bpy.props.BoolProperty(name="Reset Blender Scene on Import", default=kmsConfig['import.reset'])
    texture_mode: bpy.props.EnumProperty(name="Textures", items=texture_modes, default=kmsConfig['import.texmode'], update=changeTextureMode)
    texture_path: bpy.props.StringProperty(name="Load Path:", default=defaultTexturePaths[kmsConfig['import.texmode']])
    texture_overwrite: bpy.props.BoolProperty(name="Re-extract existing", default=kmsConfig['import.ctxr_replace'])
    merge_material_slots: bpy.props.BoolProperty(name="Merge Similar Material Slots", default=kmsConfig['import.merge_mat'])
    
    files: bpy.props.CollectionProperty(
        name="KMS files",
        type=bpy.types.OperatorFileListElement, 
        options={"HIDDEN","SKIP_SAVE"},
    )

    directory: bpy.props.StringProperty(
        subtype='DIR_PATH',
    )
    
        
    def execute(self, context):
        from . import kms_importer
        from ...tri.tri import TRI
        if self.reset_blend:
            kms_importer.reset_blend()


        for file in self.files:
            kms_path = os.path.join(self.directory, file.name)
            print("Loading", kms_path, "with textures", self.texture_mode)
            
            dirname, kms_name = os.path.split(kms_path)
            if self.texture_mode != 'none':
                extract_path = os.path.join(dirname, "sealouse_extract")
                os.makedirs(extract_path, exist_ok=True)
            if self.texture_mode == 'tri':
                if os.path.isabs(self.texture_path):
                    tri_dir = self.texture_path
                else:
                    tri_dir = os.path.join(dirname, self.texture_path)
                tri_name = triNameFromModel(kms_path, "kms")

                if tri_name is None or not os.path.exists(os.path.join(tri_dir, tri_name)):
                    tri_path = os.path.join(tri_dir, replaceExt(kms_name, "tri"))
                else:
                    tri_path = os.path.join(tri_dir, tri_name)

                print("Attempting to load TRI:", tri_path)
                if os.path.exists(tri_path):
                    tri = TRI()
                    with open(tri_path, "rb") as f:
                        tri.fromFile(f)
                    tri.dumpTextures(extract_path)
            
            if self.texture_mode == 'ctxr':
                # Unless you want to unpack every ctxr in advance, this has to be in the kms loader.
                if os.path.isabs(self.texture_path):
                    kms_importer.main(kms_path, self.texture_path, self.texture_overwrite, self.merge_material_slots)
                else:
                    kms_importer.main(kms_path, os.path.join(dirname, self.texture_path), self.texture_overwrite, self.merge_material_slots)
            else:
                kms_importer.main(kms_path, merge_material_slots = self.merge_material_slots)
                
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "reset_blend")
        col.prop(self, "texture_mode")
        if self.texture_mode != 'none':
            col.prop(self, "texture_path")
        if self.texture_mode == 'ctxr':
            col.prop(self, "texture_overwrite")
        col.prop(self, "merge_material_slots")
        col.label(text="(breaks KMS export)")
    
    
