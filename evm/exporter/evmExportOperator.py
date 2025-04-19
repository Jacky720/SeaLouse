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

    make_cmdl: bpy.props.BoolProperty(name="Generate .cmdl in _win directory", default=True)

    def execute(self, context):
        from . import evm_exporter
        if not bpy.data.collections.get("EVM") or len(bpy.data.collections["EVM"].children) == 0:
            assert(False) # No collection to export
        elif len(bpy.data.collections["EVM"].children) > 1:
            assert(False) # Multi-export not yet supported (TODO)
        else:
            colName = bpy.data.collections["EVM"].children[0].name
            print("Saving", self.filepath)
            evm_exporter.main(self.filepath, colName)
            print('EVM COMPLETE :)')
            if self.make_cmdl:
                from ...cmdl.exporter import cmdl_exporter
                split_path = os.path.split(self.filepath)
                cmdl_basename = split_path[1].replace(".evm", ".cmdl")
                cmdl_path = os.path.join(split_path[0], "_win", cmdl_basename)
                print("Saving", cmdl_path)
                cmdl_exporter.main(cmdl_path, colName, True)
                print('CMDL COMPLETE :)')
        return {'FINISHED'}
