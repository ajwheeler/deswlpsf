# copy weightmap and bad-pixel HDUs from real images to simulated ones.
# (because they were used for the simulations)
# also copy header entries!
# also run funzip

import subprocess
from astropy.io import fits

#these will need to be changed
real_fn = "/Users/adamwheeler/Dropbox/y1_test/DECam_00241238_{}.fits"
sim_fn = "/Users/adamwheeler/galsim_extra/examples/output/sim_DECam_00241238_{}.fits"

output_fn = "sims/sim_DECam_00241238_{}.fits"

print( "{} + {} -> {}".format(sim_fn, real_fn, output_fn))
print("")


for no in [f'{n:02}' for n in range(1,30) if n != 31 and n!= 61]:
    #decompress with funzip
    cmd = "funpack " + sim_fn.format(no) + ".fz"
    subprocess.call(cmd, shell=True)
    
    #copy hdus and headers
    reals = fits.open(real_fn.format(no))
    reals.verify('fix')
    sims = fits.open(sim_fn.format(no))
    sims.verify('fix')
    hdus = fits.HDUList([sims[0], reals[1], reals[2]])
    for key in reals[0].header.keys():
        if key in ['DATE-OBS', 'FILTER', 'CCDNUM', 'DETPOS', 'TELRA', 'TELDEC', 'HA']:
            sims[0].header[key] = reals[0].header[key]

    #save to sims dir
    hdus.writeto(output_fn.format(no), overwrite=True)

    
