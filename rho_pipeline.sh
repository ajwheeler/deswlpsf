#! /bin/sh
EXP=00241238
python3 build_exp_catalog.py --work sims --exps $EXP --runs 1 --output sims/exposure_info.fits
python3 build_psf_cats.py --work sims --exps $EXP --runs 1 --input sims --output sims
python3 run_rho2.py --work sims --exps $EXP --runs 1  
python3 plot_rho.py --work sims 

