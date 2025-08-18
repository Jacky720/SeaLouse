import bpy
from bpy_extras.io_utils import ImportHelper
import os
from ..ctxr import CTXR
from ...util.util import replaceExt


class ImportMgsCtxr(bpy.types.Operator, ImportHelper):
    '''Dump an MGS2 CTXR File.'''
    bl_idname = "import_scene.ctxr_data"
    bl_label = "Dump CTXR Data"
    bl_options = {'PRESET'}
    filename_ext = ".ctxr"
    filter_glob: bpy.props.StringProperty(default="*.ctxr", options={'HIDDEN'})

    #reset_blend: bpy.props.BoolProperty(name="Reset Blender Scene on Import", default=True)
    bulk_import: bpy.props.BoolProperty(name="Bulk extract (not recommended)", default=False)

    def execute(self, context):
        if self.bulk_import:
            filelist = [x for x in os.listdir(os.path.dirname(self.filepath)) if x.endswith(".ctxr")]
        else:
            filelist = [os.path.basename(self.filepath)]
        
        base_dir = os.path.dirname(self.filepath)
        extract_dir = os.path.join(base_dir, "sealouse_extract")
        os.makedirs(extract_dir, exist_ok=True)
        
        for file in filelist:
            filepath = os.path.join(base_dir, file)
            outpath = os.path.join(extract_dir, replaceExt(file, "dds"))
            print("\n\nLoading", filepath)
            
            ctxr = CTXR()
            with open(filepath, "rb") as f:
                ctxr.fromFile(f)
            dds = ctxr.convertDDS()
            with open(outpath, "wb") as f:
                dds.writeToFile(f)
        return {'FINISHED'}
