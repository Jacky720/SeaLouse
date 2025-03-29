import bpy
from bpy_extras.io_utils import ImportHelper
import os
from .tri import TRI


class ImportMgsTri(bpy.types.Operator, ImportHelper):
    '''Dump an MGS2 TRI File.'''
    bl_idname = "import_scene.tri_data"
    bl_label = "Dump TRI Data"
    bl_options = {'PRESET'}
    filename_ext = ".tri"
    filter_glob: bpy.props.StringProperty(default="*.tri", options={'HIDDEN'})

    #reset_blend: bpy.props.BoolProperty(name="Reset Blender Scene on Import", default=True)
    bulk_import: bpy.props.BoolProperty(name="Bulk extract from folder", default=False)

    def execute(self, context):
        if self.bulk_import:
            filelist = [x for x in os.listdir(os.path.split(self.filepath)[0]) if x.endswith(".tri")]
        else:
            filelist = [os.path.split(self.filepath)[1]]
        
        extract_dir = os.path.split(self.filepath)[0]
        extract_dir = os.path.join(extract_dir, "sealouse_extract")
        os.makedirs(extract_dir, exist_ok=True)
        
        for file in filelist:
            filepath = os.path.join(os.path.split(self.filepath)[0], file)
            print("\n\nLoading", filepath)
            
            myTri = TRI()
            with open(filepath, "rb") as f:
                myTri.fromFile(f)
            myTri.dumpTextures(extract_dir)
        return {'FINISHED'}