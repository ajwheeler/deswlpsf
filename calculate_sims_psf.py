#/usr/bin/env python3
# run sextractor and psfex to extract psf info from these files.
import sys
import subprocess
import os

config_dir = '.' #"/Users/adamwheeler/Dropbox/Niall"
sims_dir = 'sims'
nchips = 30
prefix = "sim_DECam_00241238"

files = os.listdir(sims_dir)

for index in [str(i+1).zfill(2) for i in range(nchips)]:
    if "{}_{}.fits".format(prefix,index) not in files:
        print("WARNING: skipping chip " + index)
        continue

    sex_cmd = ("sex "\
            + "-c {config}/psfex.sex "\
            + "{sims}/{prefix}_{i}.fits'[0]' "\
            + "-WEIGHT_IMAGE {sims}/{prefix}_{i}.fits'[2]' "\
            + "-CATALOG_NAME {sims}/{prefix}_{i}_psfcat.fits "\
            + "-PARAMETERS_NAME {config}/psfex.param "\
            + "-FILTER_NAME {config}/default.conv"\
            ).format(config=config_dir, i=index, sims=sims_dir, prefix=prefix)
    print(sex_cmd)
    subprocess.call(sex_cmd, shell=True)

    psf_cmd = ("psfex "\
            + "-c {config}/config.psfex "\
            + "{sims}/{prefix}_{i}_psfcat.fits "\
            + "-OUTCAT_NAME {sims}/{prefix}_{i}_psfcat.used.fits"\
            ).format(config=config_dir, sims=sims_dir, i=index, prefix=prefix)
    print(psf_cmd)
    subprocess.call(psf_cmd, shell=True)
