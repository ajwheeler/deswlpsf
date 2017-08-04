DES PSF stuff
=============
rho stats for simulated images
------------------------------

1. Simulate images: This will require GalSim, as well as galsim_extra (specifically [this fork](https://github.com/ajwheeler/galsim_extra), which will potentially be merged into galsim_extra soon). Go to `galsim_extra/examples` and run `galsim realistic.yaml`.

2. Edit `copy.py` and change the two relevant directories at the top of the file, then run it.  This script will decompress each simulated image, copy the bad_pixel map and weightmap and header information from the its real counterpart, and put it in the `sims` dir.



More Plots
----------
To generate plots like these run `python plots.py`.  You'll haev to change the file locations.
![histogram](https://raw.githubusercontent.com/ajwheeler/deswlpsf/master/histogram_example.png "histogram")
![image](https://raw.githubusercontent.com/ajwheeler/deswlpsf/master/image_example.png "image")

TODO:
- calculate_sims_psf.py
- plots.py
- size_mag.py
