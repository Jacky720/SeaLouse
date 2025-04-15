import bpy
from bpy_extras.io_utils import ImportHelper


class ImportMgsEvm(bpy.types.Operator, ImportHelper):
    '''Load an MGS2 EVM File.'''
    bl_idname = "import_scene.evm_data"
    bl_label = "Import EVM Data"
    bl_options = {'PRESET'}
    filename_ext = ".evm"
    filter_glob: bpy.props.StringProperty(default="*.evm", options={'HIDDEN'})

    reset_blend: bpy.props.BoolProperty(name="Reset Blender Scene on Import", default=True)
    useTri: bpy.props.BoolProperty(name="Attempt to load .tri file", default=True)

    def execute(self, context):
        print("Loading", self.filepath)
        from . import evm_importer
        if self.reset_blend:
            evm_importer.reset_blend()
        return evm_importer.main(self.filepath, self.useTri)
