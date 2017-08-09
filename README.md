DES PSF stuff
=============

*NOTE: all python code in this repo is written to python 3*

rho stats for simulated images
------------------------------

1. Simulate images: This will require GalSim, as well as galsim_extra (specifically [this fork](https://github.com/ajwheeler/galsim_extra), which will potentially be merged into galsim_extra soon). Go to `galsim_extra/examples` and run `galsim realistic.yaml`.

2. Edit `copy_fits.py` and change the two relevant directories at the top of the file, then run it (`python3 copy_fits.py`).  This script will copy the bad_pixel map and weightmap and header information from the its real counterpart and put it in the `sims` dir.

3. Run `python3 calculate_sims_psf.py` to run sextractor and psfex on each of the sims.

4. Run `./rho_pipeline.sh`.  This script runs a few utilities in modified form from https://github.com/rmjarvis/DESWL.

If all went acording to plan, you should now have a couple plots like this one:
![rho1](https://raw.githubusercontent.com/ajwheeler/deswlpsf/master/figures/rho1_all_%5Bb'r'%5D.png "rho1")

More Plots
----------
To generate plots like these run `python plots.py`.  You'll have to change the file locations at the top of the file.
![histogram](https://raw.githubusercontent.com/ajwheeler/deswlpsf/master/figures/histogram.png "histogram")
![image](https://raw.githubusercontent.com/ajwheeler/deswlpsf/master/figures/image.png "image")


To generate size-magnitude plots like this, use `size_mag.py`. If you want to fit the locus correctly, you may have to adjust some parameters, but it's a simple script.
![size-mag](https://raw.githubusercontent.com/ajwheeler/deswlpsf/master/figures/size_mag.png "size_mag")

TODO:
- size_mag.py
- can I remove any files?
