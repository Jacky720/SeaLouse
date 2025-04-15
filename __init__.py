# Blender Add-on Template
# Contributor(s): Aaron Powell (aaron@lunadigital.tv)
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
        "name": "SeaLouse",
        "description": "Import and export models for Metal Gear Solid 2.",
        "author": "Jacky720",
        "version": (0, 1),
        "blender": (2, 80, 0),
        # "location": "Properties > Render > My Awesome Panel",
        # "warning": "", # used for warning icon and text in add-ons panel
        # "wiki_url": "http://my.wiki.url",
        # "tracker_url": "http://my.bugtracker.url",
        # "support": "COMMUNITY",
        "category": "Import-Export"
        }

import bpy
from .kms.importer.kmsImportOperator import ImportMgsKms
from .kms.exporter.kmsExportOperator import ExportMgsKms
from .evm.importer.evmImportOperator import ImportMgsEvm
from .evm.exporter.evmExportOperator import ExportMgsEvm
from .tri.importer.triImportOperator import ImportMgsTri
from .util.utilOperators import SealouseObjectMenu, SLObjectClasses

#
# Add additional functions here
#

classes = {
    ImportMgsKms,
    ExportMgsKms,
    ImportMgsTri,
    ImportMgsEvm,
    #ExportMgsEvm,
}.union(SLObjectClasses)

def menu_func_import(self, context):
    self.layout.operator(ImportMgsKms.bl_idname, text="KMS File for MGS2 (.kms)")
    self.layout.operator(ImportMgsEvm.bl_idname, text="EVM File for MGS2 (.evm)")
    self.layout.operator(ImportMgsTri.bl_idname, text="Dump TRI textures for MGS2 (.tri)")

def menu_func_export(self, context):
    self.layout.operator(ExportMgsKms.bl_idname, text="KMS File for MGS2 (.kms)")

def menu_func_utils(self, context):
    self.layout.menu(SealouseObjectMenu.bl_idname)

def register():
    from . import properties
    from . import ui
    # properties.register()
    # ui.register()
    
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    bpy.types.VIEW3D_MT_object.append(menu_func_utils)

def unregister():
    from . import properties
    from . import ui
    # properties.unregister()
    # ui.unregister()
    
    for cls in classes:
        bpy.utils.unregister_class(cls)
    
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.types.VIEW3D_MT_object.remove(menu_func_utils)

if __name__ == '__main__':
    register()
