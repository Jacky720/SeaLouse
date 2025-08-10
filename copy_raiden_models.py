import os, shutil

sourcefile = "rai_def_mh_mt_stage_d005p01"
#destfiles = ["rai_radio_mh_mt"]
destfiles = ["rai_def_mh_mt_stage_w51a", "rai_def_mh_mt_stage_r_plt11_r", "rai_def_mh_mt_stage_r_plt10_r", "rai_def_mh_mt_stage_d080p06", "rai_def_mh_mt_stage_d010p01", "rai_def_mh_mt", "rai_def_addhand_mh_mt_stage_d046p01", "rai_def_addhand_mh_mt"]
#sourcefile = "rai_hair_mh_mt"
#destfiles = ["rai_hair_mh_mt_face_f01c", "rai_hair_mh_mt_stage_a41b", "rai_hair_mh_mt_stage_r_plt0_r", "rai_hair_mh_mt_stage_r_plt10_r", "rai_hair_mh_mt_stage_r_plt11_r"]
evmPathFormat = "%s.evm"
trueEvmFormat = "%s_true.evm"
cmdlPathFormat = "_win/%s.cmdl"

for destfile in destfiles:
    if not os.path.exists(trueEvmFormat % destfile):
        shutil.copyfile(evmPathFormat % destfile, trueEvmFormat % destfile)
    shutil.copyfile(evmPathFormat % sourcefile, evmPathFormat % destfile)
    shutil.copyfile(cmdlPathFormat % sourcefile, cmdlPathFormat % destfile)
    truefile = open(trueEvmFormat % destfile, "rb")
    truefile.seek(0x20)
    newfile = open(evmPathFormat % destfile, "r+b")
    newfile.seek(0x20)
    newfile.write(truefile.read(4))
    truefile.close()
    newfile.close()

print("Done! :D")