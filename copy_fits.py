# copy weightmap and bad-pixel HDUs from real images to simulated ones.
# (because they were used for the simulations)
# also copy header entries!

import subprocess
from astropy.io import fits

#these will need to be changed
real_fn = "/Users/adamwheeler/Dropbox/y1_test/DECam_00241238_{}.fits"
sim_fn = "/Users/adamwheeler/galsim_extra/examples/output/sim_DECam_00241238_{}.fits"

output_fn = "sims/sim_DECam_00241238_{}.fits"

print( "{} + {} -> {}".format(sim_fn, real_fn, output_fn))
print("")


for no in [f'{n:02}' for n in range(1,30) if n != 31 and n!= 61]:
    #copy hdus and headers
    reals = fits.open(real_fn.format(no))
    reals.verify('fix')
    sims = fits.open(sim_fn.format(no))
    sims.verify('fix')
    for key in reals[0].header.keys():
        if key in ['DATE-OBS', 'FILTER', 'CCDNUM', 'DETPOS', 'TELRA', 'TELDEC', 'HA']:
            sims[1].header[key] = reals[0].header[key]
    hdus = fits.HDUList([sims[1], reals[1], reals[2]])
    hdus.verify('fix')
    #save to sims dir
    hdus.writeto(output_fn.format(no), overwrite=True)

    
