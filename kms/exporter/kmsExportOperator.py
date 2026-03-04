import bpy
from bpy import props
from bpy_extras.io_utils import ExportHelper
import os
from ...config import kmsConfig
from ...util.util import BakFileModes, create_bak, replaceExt


class ExportMgsKms(bpy.types.Operator, ExportHelper):
    '''Save an MGS2 KMS File.'''
    bl_idname = "export_scene.kms_data"
    bl_label = "Export KMS Data"
    bl_options = {'PRESET'}
    filename_ext = ".kms"
    filter_glob: props.StringProperty(default="*.kms", options={'HIDDEN'})
    
    kms_bak: props.EnumProperty(name="Backup KMS", items=BakFileModes, default=kmsConfig['export.kms_bak'])

    make_cmdl: props.BoolProperty(name="Generate CMDL supplement", default=kmsConfig['export.make_cmdl'])
    #big_cmdl: props.BoolProperty(name="Split CMDL faces (DO NOT)", default=False)
    cmdl_path: props.StringProperty(name="CMDL Path", default=kmsConfig['export.cmdl_path'])
    cmdl_bak: props.EnumProperty(name="Backup CMDL", items=BakFileModes, default=kmsConfig['export.cmdl_bak'])
    
    make_ctxr: props.BoolProperty(name="Repack CTXR textures", default=kmsConfig['export.make_cmdl'])
    ctxr_path: props.StringProperty(name="CTXR Path", default=kmsConfig['export.ctxr_path'])
    ctxr_bak: props.EnumProperty(name="Backup CTXR", items=BakFileModes, default=kmsConfig['export.ctxr_bak'])
    
    # Override to set default file name
    def invoke(self, context, _event):
        if not self.filepath:
            if bpy.data.collections.get("KMS") and bpy.data.collections["KMS"].children:
                blend_filepath = bpy.data.collections["KMS"].children[0].name
            else:
                blend_filepath = "untitled"

            self.filepath = blend_filepath + self.filename_ext

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    def execute(self, context):
        from . import kms_exporter
        if not bpy.data.collections.get("KMS") or len(bpy.data.collections["KMS"].children) == 0:
            raise Exception("No collection to export")
        elif len(bpy.data.collections["KMS"].children) > 1:
            raise Exception("Multiple KMS subcollections found, cannot export.")
        
        collection = bpy.data.collections["KMS"].children[0]
        
        # KMS and CTXR export
        ctxr_path = None
        if self.make_ctxr:
            ctxr_path = self.makeabs(self.ctxr_path)
            os.makedirs(ctxr_path, exist_ok=True)
        
        create_bak(self.filepath, self.kms_bak)
        print("Saving", self.filepath)
        kms_exporter.main(self.filepath, collection.name, ctxr_path, self.ctxr_bak)
        print('KMS COMPLETE :)')
        
        # CMDL export
        if self.make_cmdl:
            from ...cmdl.exporter import cmdl_exporter
            cmdl_basename = replaceExt(os.path.basename(self.filepath), "cmdl")
            cmdl_path = os.path.join(self.makeabs(self.cmdl_path), cmdl_basename)
            os.makedirs(os.path.dirname(cmdl_path), exist_ok=True)
            
            create_bak(cmdl_path, self.cmdl_bak)
            print("Saving", cmdl_path)
            cmdl_exporter.main(cmdl_path, collection.name, False, False)
            print('CMDL COMPLETE :)')
        
        
        return {'FINISHED'}
        
    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "kms_bak")
        col.prop(self, "make_cmdl")
        if self.make_cmdl:
            col.prop(self, "cmdl_path")
            col.prop(self, "cmdl_bak")
        col.prop(self, "make_ctxr")
        if self.make_ctxr:
            col.prop(self, "ctxr_path")
            col.prop(self, "ctxr_bak")

    def makeabs(self, path: str) -> str:
        if os.path.isabs(path):
            return path
        else:
            return os.path.join(os.path.dirname(self.filepath), path)
