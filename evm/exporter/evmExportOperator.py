import bpy
from bpy_extras.io_utils import ExportHelper
import os


class ExportMgsEvm(bpy.types.Operator, ExportHelper):
    '''Save an MGS2 EVM File.'''
    bl_idname = "export_scene.evm_data"
    bl_label = "Export EVM Data"
    bl_options = {'PRESET'}
    filename_ext = ".evm"
    filter_glob: bpy.props.StringProperty(default="*.evm", options={'HIDDEN'})

    make_cmdl: bpy.props.BoolProperty(name="Generate CMDL supplement", default=True)
    big_cmdl: bpy.props.BoolProperty(name="Split CMDL faces (DO NOT)", default=False)
    cmdl_path: bpy.props.StringProperty(name="CMDL Path:", default="_win/")
    pack_textures: bpy.props.BoolProperty(name="Repack CTXR textures", default=False)
    tex_path: bpy.props.StringProperty(name="CTXR Path:", default="../../../textures/flatlist/ovr_stm/_win/")

    def execute(self, context):
        from . import evm_exporter
        if not bpy.data.collections.get("EVM") or len(bpy.data.collections["EVM"].children) == 0:
            raise Exception("No collection to export")
        elif len(bpy.data.collections["EVM"].children) > 1:
            raise Exception("Multiple EVM subcollections found, cannot export.")
        
        colName = bpy.data.collections["EVM"].children[0].name
        tex_path = None
        if self.pack_textures:
            if os.path.isabs(self.tex_path):
                tex_path = self.tex_path
            else:
                tex_path = os.path.join(os.path.dirname(self.filepath), self.tex_path)
            os.makedirs(tex_path, exist_ok=True)
        print("Saving", self.filepath)
        evm_exporter.main(self.filepath, colName, tex_path)
        print('EVM COMPLETE :)')
        
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
