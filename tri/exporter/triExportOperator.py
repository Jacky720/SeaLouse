import bpy
from bpy import props
from bpy_extras.io_utils import ExportHelper
import os
from ...util.util import BakFileModes, create_bak, replaceExt


class ExportMgsTri(bpy.types.Operator, ExportHelper):
    '''Save an MGS2 TRI File (minimal entry info) (and bp_assets.txt).'''
    bl_idname = "export_scene.tri_data"
    bl_label = "Export TRI Metadata"
    bl_options = {'PRESET'}
    filename_ext = ".tri"
    filter_glob: props.StringProperty(default="*.tri", options={'HIDDEN'})
    
    tri_bak: props.EnumProperty(name="Backup TRI", items=BakFileModes, default=1)
    
    make_stage: props.BoolProperty(name="Expand bp_assets.txts", default=False)
    stage_path: props.StringProperty(name="Stage Path", default="../../../eu/stage/")
    stage_bak: props.EnumProperty(name="Backup TXT", items=BakFileModes, default=1)
    
    # Multi-file handler
    files: bpy.props.CollectionProperty(
        name="TRI files",
        type=bpy.types.OperatorFileListElement, 
        options={"HIDDEN","SKIP_SAVE"},
    )

    directory: bpy.props.StringProperty(
        subtype='DIR_PATH',
    )
    
    # Override to set default file name
    def invoke(self, context, _event):
        colName = "KMS" if bpy.data.collections.get("KMS") else "EVM"
        if not self.filepath:
            if bpy.data.collections.get(colName) and bpy.data.collections[colName].children:
                blend_filepath = bpy.data.collections[colName].children[0].name
            else:
                blend_filepath = "untitled"

            self.filepath = blend_filepath + self.filename_ext

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    def execute(self, context):
        from . import tri_exporter
        colName = "KMS" if bpy.data.collections.get("KMS") else "EVM"
        if not bpy.data.collections.get(colName) or len(bpy.data.collections[colName].children) == 0:
            raise Exception("No collection to export")
        elif len(bpy.data.collections[colName].children) > 1:
            raise Exception(f"Multiple {colName} subcollections found, cannot export.")
        
        collection = bpy.data.collections[colName].children[0]
        amt = [x for x in collection.all_objects if x.type == "ARMATURE"][0]
        
        for file in self.files:
            tri_path = os.path.join(self.directory, file.name)
            # TRI export
            create_bak(tri_path, self.tri_bak)
            print('Saving', tri_path)
            tri_exporter.main(tri_path, collection, self.makeabs(self.stage_path) if self.make_stage else None, self.stage_bak)
            print('TRI COMPLETE :)')
        
        return {'FINISHED'}
        
    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, "tri_bak")
        col.prop(self, "make_stage")
        if self.make_stage:
            col.prop(self, "stage_path")
            col.prop(self, "stage_bak")

    def makeabs(self, path: str) -> str:
        if os.path.isabs(path):
            return path
        else:
            return os.path.join(os.path.dirname(self.filepath), path)
