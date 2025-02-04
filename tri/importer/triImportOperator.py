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

    def execute(self, context):
        print("Loading", self.filepath)
        
        myTri = TRI()
        with open(self.filepath, "rb") as f:
            myTri.fromFile(f)
        extract_dir = os.path.split(self.filepath)[0]
        extract_dir = os.path.join(extract_dir, "sealouse_extract")
        os.makedirs(extract_dir, exist_ok=True)
        myTri.dumpTextures(extract_dir)
        return {'FINISHED'}