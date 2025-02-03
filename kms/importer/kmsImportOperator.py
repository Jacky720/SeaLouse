import bpy
from bpy_extras.io_utils import ImportHelper


class ImportMgsKms(bpy.types.Operator, ImportHelper):
    '''Load an MGS2 KMS File.'''
    bl_idname = "import_scene.kms_data"
    bl_label = "Import KMS Data"
    bl_options = {'PRESET'}
    filename_ext = ".kms"
    filter_glob: bpy.props.StringProperty(default="*.kms", options={'HIDDEN'})

    reset_blend: bpy.props.BoolProperty(name="Reset Blender Scene on Import", default=True)

    def execute(self, context):
        print("Loading", self.filepath)
        from . import kms_importer
        if self.reset_blend:
            kms_importer.reset_blend()
        return kms_importer.main(self.filepath)