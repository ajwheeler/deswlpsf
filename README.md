DES PSF stuff
=============

*NOTE: all python code in this repo is written to python 3*

rho stats for simulated images
------------------------------

1. Simulate images: This will require GalSim, as well as galsim_extra (specifically [this fork](https://github.com/ajwheeler/galsim_extra), which will potentially be merged into galsim_extra soon). Go to `galsim_extra/examples` and run `galsim realistic.yaml`.

2. Edit `copy_fits.py` and change the two relevant directories at the top of the file, then run it (`python3 copy_fits.py`).  This script will copy the bad_pixel map and weightmap and header information from the its real counterpart and put it in the `sims` dir.

3. Run `python3 calculate_sims_psf.py` to run sextractor and psfex on each of the sims.

4. Run `./rho_pipeline.sh`.  This script runs a few utilities in modified form from [https://github.com/rmjarvis/DESWL].

More Plots
----------
To generate plots like these run `python plots.py`.  You'll have to change the file locations.
![histogram](https://raw.githubusercontent.com/ajwheeler/deswlpsf/master/histogram_example.png "histogram")
![image](https://raw.githubusercontent.com/ajwheeler/deswlpsf/master/image_example.png "image")

TODO:
- calculate_sims_psf.py
- size_mag.py
- why are the pixel histograms all mismatched?
