import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from astropy.modeling import polynomial, fitting

def real_in_locus(c):
    x,y = c.mag, c.radius
    return (x < -11) & (y < 2.7) & (y > 2)

def sim_in_locus(c):
    x,y = c.mag, c.radius
    return (x < -11) & (y < 2.6) & (y > 2)

cols = ('num', 'mag', 'x', 'y', 'stelarity', 'radius')
kwargs = {'sep': '\s+', 'names': cols, 'index_col': 0, 'comment': '#'}
real_cat = pd.read_table("real.cat", **kwargs)
sim_cat = pd.read_table('sim.cat', **kwargs)

for (name, cat, in_locus) in [('real', real_cat, real_in_locus), \
                              ('sim', sim_cat, sim_in_locus)]:
    print(name + " catalog. . .")

    locus = cat[in_locus(cat)]
    other = cat[np.invert(in_locus(cat))]
    print("There are {} (out of {}) sources along the locus".format(len(locus), len(other)))

    model0 = polynomial.Polynomial1D(1)
    fitter = fitting.LinearLSQFitter()
    model = fitter(model0, locus.mag, locus.radius)
    print("best fit params are {}".format(model.parameters))

    plt.plot(locus.mag, model(locus.mag), ls='--', lw=0.5, color='black')
    plt.scatter(x=locus.mag, y=locus.radius, s=1, c='r')
    plt.scatter(x=other.mag, y=other.radius, s=1, c='b')
    plt.ylim((1, 8))
    plt.xlabel('radius')
    plt.ylabel('mag')
    plt.savefig(name + "_size_mag.png")
    plt.clf()

    print("")
