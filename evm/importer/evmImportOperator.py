import bpy
from bpy_extras.io_utils import ImportHelper
import os

texture_modes = [
    ('none', 'No Textures', 'Do not load textures'),
    ('tri', 'Unpack .tri', 'Unpack .tga from .tri file'),
    ('ctxr', 'Unpack .ctxr', 'Unpack .png from .ctxr files')
]

def changeTextureMode(self, context):
    if self.texture_mode == 'tri':
        if self.texture_path == "" or self.texture_path == "../../../textures/flatlist/_win/":
            self.texture_path = "../../tri/us/"
    if self.texture_mode == 'ctxr':
        if self.texture_path == "" or self.texture_path == "../../tri/us/":
            self.texture_path = "../../../textures/flatlist/_win/"

class ImportMgsEvm(bpy.types.Operator, ImportHelper):
    '''Load an MGS2 EVM File.'''
    bl_idname = "import_scene.evm_data"
    bl_label = "Import EVM Data"
    bl_options = {'PRESET'}
    filename_ext = ".evm"
    filter_glob: bpy.props.StringProperty(default="*.evm", options={'HIDDEN'})

    reset_blend: bpy.props.BoolProperty(name="Reset Blender Scene on Import", default=True)
    texture_mode: bpy.props.EnumProperty(name="Textures", items=texture_modes, default=0, update=changeTextureMode)
    texture_path: bpy.props.StringProperty(name="Load Path:")
    texture_overwrite: bpy.props.BoolProperty(name="Re-extract existing", default=False)

    def execute(self, context):
        print("Loading", self.filepath, "with textures", self.texture_mode)
        from . import evm_importer
        from ...tri.tri import TRI
        if self.reset_blend:
            evm_importer.reset_blend()
        
        dirname, kms_name = os.path.split(self.filepath)
        if self.texture_mode != 'none':
            extract_path = os.path.join(dirname, "sealouse_extract")
            os.makedirs(extract_path, exist_ok=True)
        if self.texture_mode == 'tri':
            if os.path.isabs(self.texture_path):
                tri_path = os.path.join(self.texture_path, replaceExt(kms_name, "tri"))
            else:
                tri_path = os.path.join(dirname, self.texture_path, replaceExt(kms_name, "tri"))
            
            if os.path.exists(tri_path):
                tri = TRI()
                with open(tri_path, "rb") as f:
                    tri.fromFile(f)
                tri.dumpTextures(extract_path)
        
        if self.texture_mode == 'ctxr':
            # Unless you want to unpack every ctxr in advance, this has to be in the kms loader.
            if os.path.isabs(self.texture_path):
                return evm_importer.main(self.filepath, self.texture_path, self.texture_overwrite)
            else:
                return evm_importer.main(self.filepath, os.path.join(dirname, self.texture_path), self.texture_overwrite)
        else:
            return evm_importer.main(self.filepath)
        
    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "reset_blend")
        col.prop(self, "texture_mode")
        if self.texture_mode != 'none':
            col.prop(self, "texture_path")
        if self.texture_mode == 'ctxr':
            col.prop(self, "texture_overwrite")
