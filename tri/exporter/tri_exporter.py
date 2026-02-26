import bpy
from os import path
from ..tri import TRI, TRIEntry
from ...util.materials import compute_hash, TextureSave
from ...util.util import create_bak

def main(tri_path: str, col: bpy.types.Collection, stage_path: str = None, stage_bak: str = 'nexist'):
    amt = [x for x in col.all_objects if x.type == "ARMATURE"][0]
    tri_name = path.basename(tri_path).split('.')[0]
    amt['strcode'] = compute_hash(tri_name)
    
    # Read existing TRI if possible
    if path.exists(tri_path):
        with open(tri_path, "rb") as tri_fp:
            tri = TRI().fromFile(tri_fp)
    else:
        tri = TRI()
    
    # Iterate materials in scene, save them
    texIDs = [x.texID for x in tri.textures]
    texSave = TextureSave()
    for mat in bpy.data.materials:  # TODO: Should iterate only collection objects
        for matType in ["color", "specular", "environment"]:
            texID = texSave.get_map(mat, matType)
            if texID == 0 or texID in texIDs:
                continue
            texIDs.append(texID)
            
            newEntry = TRIEntry()
            newEntry.texID = texID
            newEntry.texType = 68  # Color map
            if matType == "specular":
                newEntry.texType = 66  # Specular map
            if matType == "environment":
                newEntry.texType = 88  # Environment map
            
            if len(tri.textures) > 0:  # idk if necessary, better safe than sorry
                newEntry.registerInfo1 = tri.textures[0].registerInfo1
                newEntry.registerInfo2 = tri.textures[0].registerInfo2
            
            tri.textures.append(newEntry)
    
    with open(tri_path, "wb") as tri_fp:
        tri.writeToFile(tri_fp)
    
    if stage_path:
        for stage in os.listdir(stage_path):
            export_stage(tri_name, os.path.join(stage_path, stage), texSave, stage_bak)


def export_stage(tri_name: str, stage_path: str, texSave: TextureSave, stage_bak: str = 'nexist'):
    # ex. "r_plt0"
    stage_folder = os.path.basename(stage_path)
    if stage_folder.startswith('r_'):
        subfoldermode = 'resident'
    else:
        subfoldermode = 'cache'
    # First, scan manifest.txt for tri reference.
    manifest_path = os.path.join(stage_path, "manifest.txt")
    if os.path.exists(manifest_path):
        with open(manifest_path, "rt") as manifest_fp:
            lines = manifest_fp.read().split("\n\n")[:-1]
    else:
        return
    
    if all(tri_name not in line for line in lines):
        return
    
    print("Editing bp_assets.txt in", stage_folder)
    # Get the hash used by this particular tri, may not be standard
    line = [x for x in lines if tri_name in x][0]
    tri_hash: str = line.split('/')[-1][:8]
    # Next, bp_assets.txt. This contains ctxrs, then cmdls
    # We are only worried about ctxr
    assets_path = os.path.join(stage_path, "bp_assets.txt")
    if os.path.exists(assets_path):
        with open(assets_path, "rt") as assets_fp:
            lines = assets_fp.read().split("\n\n")[:-1]
    else:
        print("WARN: Missing bp_assets.txt?")
        lines = []
    prepend = []
    for image in texSave.textures_to_save:
        texName = replaceExt(image.name, "ctxr")
        line = ','.join([
          os.path.join("textures/flatlist/", texName),
          os.path.join("stage/", stage_folder, subfoldermode, texName),
          os.path.join("eu/stage/", stage_folder,
                       subfoldermode, tri_hash,
                       f"{compute_hash(texName.split('.')[0]):08x}.ctxr")
        ]).replace('\\', '/')  # windows, shut up
        if any(line in line2 for line2 in lines):
            continue  # Duplicate, possibly double export
        prepend.append(line)
    
    if len(prepend) > 0:
        lines = prepend + lines
        create_bak(assets_path, stage_bak)
        write_weird_txt(assets_path, lines)


def write_weird_txt(path: str, lines: list[str]):
    with open(path, "wb") as fp:
        for line in lines:
            fp.write(line.encode('utf-8'))
            fp.write(b"\r\r\n")  # Whyyyyy Bluepoint
    print(f'Saved {os.path.basename(path)}! :)')
