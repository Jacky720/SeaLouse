import os, shutil, struct
from ..tri.tri import tri_lookup_path


RAW_NORMAL_ATTR = "sealouse_raw_normal"
RAW_POSITION_ATTR = "sealouse_raw_position"
_POSITION_EPSILON = 1e-6  # float noise floor

def setRawNormalAttribute(objmesh, normals):
    attr = objmesh.attributes.new(name=RAW_NORMAL_ATTR, type='FLOAT_VECTOR', domain='POINT')
    attr.data.foreach_set("vector", [c for n in normals for c in n])

def setRawPositionAttribute(objmesh, vertices):
    attr = objmesh.attributes.new(name=RAW_POSITION_ATTR, type='FLOAT_VECTOR', domain='POINT')
    attr.data.foreach_set("vector", [c for v in vertices for c in v])

# store original vert positions on import, and skip normal recalculation if a specific face's verts haven't actually changed.
# not 100% neccasary, but ensures that everything's exactly as it original was just incase blender changes something in the future.
def computeStableVertices(mesh):

    pos_attr = mesh.attributes.get(RAW_POSITION_ATTR)
    if pos_attr is None:
        return frozenset()
    if len(pos_attr.data) != len(mesh.vertices):

        return frozenset()
    unchanged = set()
    for i, v in enumerate(mesh.vertices):
        stored = pos_attr.data[i].vector
        if (stored - v.co).length < _POSITION_EPSILON:
            unchanged.add(i)
    if not unchanged:
        return frozenset()
    neighbors = {}
    for poly in mesh.polygons:
        vs = poly.vertices
        for vi in vs:
            neighbors.setdefault(vi, set()).update(vs)
    stable = set()
    for vi in unchanged:
        adj = neighbors.get(vi)
        if adj is None or adj.issubset(unchanged):
            stable.add(vi)
    return frozenset(stable)


def getRawNormal(mesh, vertex_index, live_normal, stableVertices):

    if vertex_index not in stableVertices:
        return live_normal
    attr = mesh.attributes.get(RAW_NORMAL_ATTR)
    if attr is None or vertex_index >= len(attr.data):

        return live_normal
    return attr.data[vertex_index].vector

kmsBoneNameArray = [
    # Tuples indicate a bone that we would prefer to map differently with MGR models (I like MGR)
    "HIP",
    "spine_1",
    ("spine_2", "spine_3"),
    "shoulder_R", # bone3
    "upper_arm_R",
    "lower_arm_R",
    ("wrist_R", "hand_R"),
    "shoulder_L", # bone7
    "upper_arm_L",
    "lower_arm_L",
    ("wrist_L", "hand_L"),
    "neck", # bone11
    "head",
    "upper_leg_R", # bone13
    "lower_leg_R",
    "foot_R",
    "toe_R",
    "upper_leg_L", # bone17
    "lower_leg_L",
    "foot_L",
    "toe_L",
    "head_2", # bone21 - duplicate of bone12, gets all the weights on EVM
    "lower_lip_side_L", # bone22
    "lower_lip_side_R",
    "lower_lip_corner_L",
    "lower_lip_corner_R",
    "eye_L", # bone26
    "eye_R",
    "eyebrow_upper_L", # bone28
    "eyebrow_L",
    "eyebrow_lower_L",
    "eyebrow_upper_R",
    "eyebrow_R",
    "eyebrow_lower_R",
    "upper_lip_side_L", # bone34
    "upper_lip_side_R",
    "upper_lip_corner_L",
    "upper_lip_corner_R",
    "outer_cheek_L", # bone38
    "outer_cheek_R",
    "nostril_L", # bone40
    "nostril_R",
    "jaw", # bone42
    "inner_cheek_L", # bone43
    "inner_cheek_R",
    ("lower_eyelid_L", "lower_eyelid_1_L"),
    ("lower_eyelid_R", "lower_eyelid_1_R"),
    ("corner_eyelid_L", "lower_eyelid_2_L"),
    "upper_eyelid_2_L",
    "upper_eyelid_1_L",
    ("corner_eyelid_R", "lower_eyelid_2_R"),
    "upper_eyelid_2_R",
    "upper_eyelid_1_R" # bone52
]

kmsBoneNames = [x[0] if type(x) is tuple else x for x in kmsBoneNameArray]
mgrBoneNames = [x[1] if type(x) is tuple else x for x in kmsBoneNameArray]

expected_parent_bones = [-1, 0, 1, 2, 3, 4, 5, 2, 7, 8, 9, 2, 11, 0, 13, 14, 15, 0, 17, 18, 19]

mgrBoneMap = {x: kmsBoneNames[i] for i, x in enumerate(mgrBoneNames)}

evmFingerArray = [
    "hand",
    "index_finger_1", "index_finger_2", "index_finder_3",
    "middle_finger_1", "middle_finger_2", "middle_finger_3",
    "thumb_1", "thumb_2", "thumb_3",
    "ring_finger_1", # Misnomer: affects both ring and pinky
    "ring_finger_2", "ring_finger_3", "ring_finger_4",
    "pinkie_1", "pinkie_2", "pinkie_3"
]
evmFingerArray = [x + "_R" for x in evmFingerArray] + [x + "_L" for x in evmFingerArray]

BakFileModes = [
    ('never', 'Never', 'Do not create .bak'),
    ('nexist', 'If not exists', 'Create .bak if one does not exist'),
    ('always', 'Always', 'Create .bak on any file overwrite')
]

def create_bak(filepath: str, bakmode: str = 'nexist'):
    if bakmode == 'never':
        return
    if not os.path.exists(filepath):
        return
    if bakmode == 'always' or not os.path.exists(filepath + '.bak'):
        print("Backing up", filepath)
        shutil.copyfile(filepath, filepath + '.bak')

def getBoneName(boneIndex: int, fingerIndex: int = -1):
    if fingerIndex >= 0 and fingerIndex <= boneIndex < fingerIndex + len(evmFingerArray):
        return evmFingerArray[boneIndex - fingerIndex]
    elif 0 <= boneIndex < len(kmsBoneNames):
        return kmsBoneNames[boneIndex]
    else:
        return f"bone{boneIndex}"

def getBoneIndex(boneName: str, fingerIndex: int = 0):
    if boneName in evmFingerArray:
        return fingerIndex + evmFingerArray.index(boneName)
    elif boneName in kmsBoneNames:
        return kmsBoneNames.index(boneName)
    elif boneName.startswith("bone") and boneName[4:].isnumeric():
        return int(boneName[4:])
    raise ValueError(f"Could not recognize bone name {boneName}")

def getFingerIndex(boneNames: list[str]):
    return sum(1 if x in kmsBoneNames else 0 for x in boneNames)

def getVertWeight(vert, obj = None, group_name: str = None) -> float:
    group_index = 0
    if obj and group_name and group_name in [group.name for group in obj.vertex_groups]:
        group_index = obj.vertex_groups.values().index(obj.vertex_groups[group_name])
    else:
        print("fuck")
    for group in vert.groups:
        if group.group == group_index:
            return group.weight
    return 0.0 # vertex is only weighted to parent

def replaceExt(path: str, new_ext: str) -> str:
    return f"{os.path.splitext(path)[0]}.{new_ext}"

def stripExt(path: str) -> str:
    return os.path.splitext(path)[0]

def stripAllExt(path:str) -> str:
    p, ext = os.path.splitext(path)

    if len(ext) > 0:
        return stripAllExt(p)

    return p
    
texture_modes = [
    ('none', 'No Textures', 'Do not load textures'),
    ('tri', 'Unpack .tri', 'Unpack .png from .tri file'),
    ('ctxr', 'Unpack .ctxr', 'Unpack .png from .ctxr files')
]

defaultTexturePaths = [
    "",
    "../../tri/us/",
    "../../../textures/flatlist/_win/"
]

def changeTextureMode(self, context):
    if self.texture_path not in defaultTexturePaths:  # Don't overwrite custom
        return
    if self.texture_mode == 'tri':
        self.texture_path = defaultTexturePaths[1]
    if self.texture_mode == 'ctxr':
        self.texture_path = defaultTexturePaths[2]

def _readTriCode(modelPath: str, modelType: str = None) -> int | None:
    if modelType is None:
        modelType = os.path.splitext(modelPath)[1][-3:]
    modelType = modelType.lower()
    if modelType not in {'kms', 'evm'} or not os.path.exists(modelPath):
        return None

    with open(modelPath, "rb") as fp:
        if modelType == 'kms':
            # KMSHeader: pad @0x0C, strcode @0x10 - PS2-format files (pad != 0)
            # store the real code in pad instead, same override KMSHeader.fromFile does.
            fp.seek(0x0C)
            pad, strcode = struct.unpack("<II", fp.read(8))
            return pad if pad != 0 else strcode
        else:
            # EVMHeader: strcode @0x20, pad @0x24 - same PS2-format override as KMS,
            # just with pad following strcode instead of preceding it.
            fp.seek(0x20)
            strcode, pad = struct.unpack("<II", fp.read(8))
            return pad if pad != 0 else strcode

def triNameFromModel(modelPath: str, modelType: str = None) -> str | None:
    triCode = _readTriCode(modelPath, modelType)
    if triCode is None:
        return None

    with open(tri_lookup_path, "rt") as fp:
        for line in fp.readlines():
            if int(line.split()[1]) == triCode:
                return line.split()[2]

def gv_strcode(name: str) -> int:
    value = 0
    for c in name.encode("latin-1"):
        value = ((value << 5) | (value >> 19)) & 0xffffff
        value = (value + ord(chr(c).lower())) & 0xffffff
    if value == 0:
        value = 1
    return value

def _looksLikeStrcode(name: str) -> bool:
    # does he lookuh like a man?
    return len(name) == 6 and all(c in "0123456789abcdefABCDEF" for c in name)

# ps2 stage dumps. if tri are still original strcode, we use the strcode filename, otherwise, use gv_strcode("joydict recovered tri name") to detect the right tri.
def triPathFromHashFallback(modelPath: str, modelType: str = None) -> str | None:
    triCode = _readTriCode(modelPath, modelType)
    if triCode is None:
        return None

    searchDir = os.path.dirname(modelPath)

    # ps2 .tri without its joydict resolved alias, the actual filename is already the strcode and we can just use that directly.
    directStrcodePath = os.path.join(searchDir, f"{triCode:06x}.tri")
    if os.path.exists(directStrcodePath):
        return directStrcodePath

    for fname in os.listdir(searchDir):
        if not fname.lower().endswith(".tri"):
            continue
        name = os.path.splitext(fname)[0]
        if _looksLikeStrcode(name):
            continue  # already checked above (direct strcode match)
            #ps2 tri that have been renamed back to their original alias by arsenal w/ joydict. rehash the restored alias back to strcode (lol)
        if gv_strcode(name) == triCode:
            return os.path.join(searchDir, fname)
    return None

    return None

