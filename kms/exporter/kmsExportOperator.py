import bpy
from bpy import props
from bpy_extras.io_utils import ExportHelper
import os


class ExportMgsKms(bpy.types.Operator, ExportHelper):
    '''Save an MGS2 KMS File.'''
    bl_idname = "export_scene.kms_data"
    bl_label = "Export KMS Data"
    bl_options = {'PRESET'}
    filename_ext = ".kms"
    filter_glob: props.StringProperty(default="*.kms", options={'HIDDEN'})

    make_cmdl: props.BoolProperty(name="Generate CMDL supplement", default=True)
    big_cmdl: props.BoolProperty(name="Split CMDL faces (DO NOT)", default=False)
    cmdl_path: props.StringProperty(name="CMDL Path:", default="_win/")
    pack_textures: props.BoolProperty(name="Repack CTXR textures", default=False)
    tex_path: props.StringProperty(name="CTXR Path:", default="../../../textures/flatlist/ovr_stm/_win/")
    
    # Override to set default file name
    def invoke(self, context, _event):
        if not self.filepath:
            if bpy.data.collections.get("EVM") and bpy.data.collections["EVM"].children:
                blend_filepath = bpy.data.collections["EVM"].children[0].name
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
        
        colName = bpy.data.collections["KMS"].children[0].name
        tex_path = None
        if self.pack_textures:
            if os.path.isabs(self.tex_path):
                tex_path = self.tex_path
            else:
                tex_path = os.path.join(os.path.dirname(self.filepath), self.tex_path)
            os.makedirs(tex_path, exist_ok=True)
        print("Saving", self.filepath)
        kms_exporter.main(self.filepath, colName, tex_path)
        print('KMS COMPLETE :)')
        
        if self.make_cmdl:
            from ...cmdl.exporter import cmdl_exporter
            dirname, basename = os.path.split(self.filepath)
            cmdl_basename = basename.replace(".kms", ".cmdl")
            if os.path.isabs(self.cmdl_path):
                win_folder = self.cmdl_path
            else:
                win_folder = os.path.join(dirname, self.cmdl_path)
            os.makedirs(win_folder, exist_ok=True)
            cmdl_path = os.path.join(win_folder, cmdl_basename)
            print("Saving", cmdl_path)
            
            cmdl_exporter.main(cmdl_path, colName, False, self.big_cmdl)
            print('CMDL COMPLETE :)')
        
        return {'FINISHED'}
        
    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "make_cmdl")
        if self.make_cmdl:
            col.prop(self, "cmdl_path")
        col.prop(self, "pack_textures")
        if self.pack_textures:
            col.prop(self, "tex_path")
