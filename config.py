evmConfig = {
    "import.reset": True,
    # 0 = None, 1 = TRI, 2 = CTXR
    "import.texmode": 0,
    "import.ctxr_replace": False,
    "import.merge_mat": False, # Nicer in Blender, export issues
    "export.make_cmdl": True,
    "export.cmdl_path": "_win/",
    "export.make_ctxr": False,
    "export.ctxr_path": "../../../textures/flatlist/ovr_stm/_win/"
}
kmsConfig = {
    "import.reset": True,
    # 0 = None, 1 = TRI, 2 = CTXR
    "import.texmode": 0,
    "import.ctxr_replace": False,
    "import.merge_mat": False, # Nicer in Blender, export issues
    # 0 = Never backup, 1 = Backup if backup doesn't exist, 2 = Always backup
    "export.kms_bak": 1,
    "export.make_cmdl": True,
    "export.cmdl_path": "_win/",
    "export.cmdl_bak": 1,
    "export.make_ctxr": False,
    "export.ctxr_path": "../../../textures/flatlist/ovr_stm/_win/",
    "export.ctxr_bak": 0
}
triConfig = {
    "import.bulk": False,
    # 0 = Never backup, 1 = Backup if backup doesn't exist, 2 = Always backup
    "export.tri_bak": 1,
    # Expands all bp_assets.txt in subfolders of given folder with new textures
    "export.edit_txt": False,
    "export.txt_path": "../../../eu/stage/", # also eu/face
    "export.txt_bak": 1
}
ctxrConfig = {
    "import.bulk": False
}

