import os

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

def getBoneName(boneIndex: int, fingerIndex: int = -1):
    if fingerIndex >= 0 and boneIndex >= fingerIndex:
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
    