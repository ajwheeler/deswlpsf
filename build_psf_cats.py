# Calculate shapes of stars and the shapes of the PSFEx measurements of the stars.
import os
import numpy
import astropy.io.fits as pyfits
import galsim
import fitsio
import piff
import galsim.des

# Define the flag values:

MAX_CENTROID_SHIFT = 1.0

NOT_USED = 1
MEAS_BAD_MEASUREMENT = 2
MEAS_CENTROID_SHIFT = 4
PSFEX_BAD_MEASUREMENT = 8
PSFEX_CENTROID_SHIFT = 16
PSFEX_FAILURE = 32
RESERVED = 64
#DESDM_BAD_MEASUREMENT = 64  # Prior to y1a1-v13, this was the meaning of 64-256
#DESDM_CENTROID_SHIFT = 128
#DESDM_FAILURE = 256
#DESDM_FLAG_FACTOR = DESDM_BAD_MEASUREMENT / PSFEX_BAD_MEASUREMENT
BLACK_FLAG_FACTOR = 512 # blacklist flags are this times the original exposure blacklist flag
                        # blacklist flags go up to 64, so this uses up to 1<<15
 
def parse_args():
    import argparse
    
    parser = argparse.ArgumentParser(description='Build PSF catalogs for a set of runs/exposures')

    # Drectory arguments
    parser.add_argument('--work', default='./',
                        help='location of work directory')
    parser.add_argument('--tag', default=None,
                        help='A version tag to add to the directory name')
    parser.add_argument('--output_dir', default=None,
                        help='location of output directory (default: $DATADIR/EXTRA/red/{run}/psfex-rerun/{exp}/)')
    parser.add_argument('--input_dir', default=None,
                        help='location of input directory (default: $DATADIR/OPS/red/{run}/red/{exp}/)')
    parser.add_argument('--reference_tag', default=None,
                        help='A reference tag from which to take the PSFEx outliers used when main tag uses reserved stars')

    # Exposure inputs
    parser.add_argument('--exp_match', default='*_[0-9][0-9].fits*',
                        help='regexp to search for files in exp_dir')
    parser.add_argument('--file', default='',
                        help='list of run/exposures (in lieu of separate exps, runs)')
    parser.add_argument('--exps', default='', nargs='+',
                        help='list of exposures to run')
    parser.add_argument('--runs', default='', nargs='+',
                        help='list of runs')
    parser.add_argument('--noweight', default=False, action='store_const', const=True,
                        help='do not try to use a weight image.')


    # Options
    parser.add_argument('--single_ccd', default=False, action='store_const', const=True,
                        help='Only do 1 ccd per exposure (used for debugging)')
    parser.add_argument('--use_piff', default=False, action='store_const', const=True,
                        help='Use Piff, not PSFEx')

    args = parser.parse_args()
    return args


def get_wcs(img_file):
    """Read the wcs from the image header
    """
    hdu = 1
    im = galsim.fits.read(img_file, hdu=hdu)
    return im.wcs

def parse_file_name(file_name):
    """Parse the PSFEx file name to get the root name and the chip number
    """

    dir, base_file = os.path.split(file_name)
    if os.path.splitext(base_file)[1] == '.fz':
        base_file=os.path.splitext(base_file)[0]
    if os.path.splitext(base_file)[1] != '.fits':
        raise ValueError("Invalid file name "+file)
    root = os.path.splitext(base_file)[0]

    ccdnum = int(root.split('_')[-1])
    return dir, root, ccdnum


def read_used(exp_dir, root, use_piff=False):
    """Read in the .used.fits file that PSFEx generates with the list of stars that actually
    got used in making the PSFEx file.
    """
    import copy

    if use_piff:
        file_name = os.path.join(exp_dir, root + '_psfcat.psf')
        if not os.path.isfile(file_name):
            return None
        print('Reading used file: ',file_name)
        #data = fitsio.read(file_name, ext='psf_stars')
        data = fitsio.read(file_name)
        # Make this look like a PSFEx used file by renaming x,y -> X_IMAGE, Y_IMAGE
        assert data.dtype.names[0] == 'x'
        assert data.dtype.names[1] == 'y'
        data.dtype.names = ('X_IMAGE', 'Y_IMAGE') + data.dtype.names[2:]
    else:
        file_name = os.path.join(exp_dir, root + '_psfcat.used.fits')
        if not os.path.isfile(file_name):
            print('Used file: ',file_name,' does not exist.')
            return None
        print('Reading used file: ',file_name)
        f = pyfits.open(file_name, memmap=False)
        data = copy.copy(f[2].data)
        f.close()
        # This has the following columns:
        # SOURCE_NUMBER: 1..n
        # EXTENSION_NUMBER: Seems to be all 1's.
        # CATALOG_NUMBER: Also all 1's.
        # VECTOR_CONTEXT: nx2 array.  Seems to be the same as x,y
        # X_IMAGE: x values  (0-2048)
        # Y_IMAGE: y values (0-4096)
        # DELTAX_IMAGE: All numbers with abs val < 1.  Probably centroid shifts.
        # DELTAY_IMAGE: All numbers with abs val < 1.  Probably centroid shifts.
        # NORM_PSF: Big numbers.  I'm guessing total flux?  Possibly weighted flux.
        # CHI2_PSF: Mostly a little more than 1.  Reduced chi^2 presumably.
        # RESI_PSF: Very small numbers. <1e-4 typically.  Presumably the rms residual.
    return data

def read_reserve(exp_dir, root):
    """Read in the _reserve.fits file if it exists.
    """
    file_name = os.path.join(exp_dir, root + '_reserve.fits')
    if not os.path.isfile(file_name):
        return None
    print('Read reserve file ',file_name)
    try:
        data = fitsio.read(file_name)
    except Exception as e:
        print('Caught ',e)
        return None
    return data

def read_findstars(exp_dir, root):
    """Read in the findstars output file.
    """
    import copy

    file_name = os.path.join(exp_dir, root + '_findstars.fits')
    print('file_name = ',file_name)
    if not os.path.isfile(file_name):
        print('File does not exist.')
        # Then use the original catalog instead.
        file_name = os.path.join(exp_dir, root + '_psfcat.fits')
        print('Use file_name = ',file_name)
        try:
            with pyfits.open(file_name, memmap=False) as fp:
                data = copy.copy(fp[2].data)
            # Convert to the column names from fs.
            new_data = numpy.empty(len(data), 
                                   dtype=[('id',int), ('x',float), ('y',float),
                                          ('mag',float), ('star_flag',int)])
            new_data['id'] = data['NUMBER']
            new_data['x'] = data['X_IMAGE']
            new_data['y'] = data['Y_IMAGE']
            new_data['mag'] = data['MAG_AUTO']
            new_data['star_flag'][:] = 1
            #print 'id = ',new_data['id']
            #print 'x = ',new_data['x']
            #print 'y = ',new_data['y']
            return new_data
        except Exception as e:
            print('Caught exception:')
            print(e)
            return None
    else:
        try:
            with pyfits.open(file_name, memmap=False) as fp:
                data = copy.copy(fp[1].data)
            # This has the following columns:
            # id: The original id from the SExtractor catalog
            # x: The x position
            # y: The y position
            # sky: The local sky value
            # noise: The estimated noise.  But these are all 0, so I think this isn't being calculated.
            # size_flags: Error flags that occurred when estimating the size
            # mag: The magnitude from SExtractor
            # sg: SExtractor's star/galaxy estimate.  Currently SPREAD_MODEL
            # sigma0: The shapelet sigma that results in a b_11 = 0 shapelet parameter.
            # star_flag: 1 if findstars thought this was a star, 0 otherwise.
            return data
        except Exception as e:
            print('Caught exception:')
            print(e)
            return None
 
def find_index(x1, y1, x2, y2):
    """Find the index of the closest point in (x2,y2) to each (x1,y1)

    Any points that do not have a corresponding point within 1 arcsec gets index = -1.
    """
    index = numpy.zeros(len(x1),dtype=int)
    for i in range(len(x1)):
        close = numpy.where( (x2 > x1[i]-1.) &
                             (x2 < x1[i]+1.) &
                             (y2 > y1[i]-1.) &
                             (y2 < y1[i]+1.) )[0]
        if len(close) == 0:
            #print 'Could not find object near x,y = (%f,%f)'%(x,y)
            index[i] = -1
        elif len(close) == 1:
            index[i] = close[0]
        else:
            print('Multiple objects found near x,y = (%f,%f)'%(x1[i],y1[i]))
            amin = numpy.argmin((x2[close] - x1[i])**2 + (y2[close] - y1[i])**2)
            print('Found minimum at ',close[amin],', where (x,y) = (%f,%f)'%(
                    x2[close[amin]], y2[close[amin]]))
            index[i] = close[amin]
    return index

 
def find_fs_index(used_data, fs_data, suffix='_IMAGE'):
    """Find the index in the fs_data records corresponding to each star in used_data.
    """
    used_x = used_data['X' + suffix]
    used_y = used_data['Y' + suffix]
    fs_x = fs_data['x']
    fs_y = fs_data['y']
    return find_index(used_x, used_y, fs_x, fs_y)

def find_used_index(fs_data, used_data, suffix='_IMAGE'):
    """Find the index in the used_data records corresponding to each star in fs_data.
    """
    fs_x = fs_data['x']
    fs_y = fs_data['y']
    used_x = used_data['X' + suffix]
    used_y = used_data['Y' + suffix]
    return find_index(fs_x, fs_y, used_x, used_y)


def measure_shapes(xlist, ylist, file_name, wcs, noweight):
    """Given x,y positions, an image file, and the wcs, measure shapes and sizes.

    We use the HSM module from GalSim to do this.

    Returns e1, e2, size, flag.
    """

    #im = galsim.fits.read(file_name)
    #bp_im = galsim.fits.read(file_name, hdu=2)
    #wt_im = galsim.fits.read(file_name, hdu=3)
    print('file_name = ',file_name)
    with pyfits.open(file_name) as f:
        #print 'f = ',f
        #print 'len(f) = ',len(f)
        # Some DES images have bad cards.  Fix them with verify('fix') before sending to GalSim.
        for i in range(1,len(f)):
            f[i].verify('fix')
            #print 'f[i] = ',f[i]
        #print 'after verify, f = ',f
        if file_name.endswith('fz'):
            im = galsim.fits.read(hdu_list=f, hdu=1, compression='rice')
            if noweight:
                bp_im = wt_im = None
            else:
                bp_im = galsim.fits.read(hdu_list=f, hdu=2, compression='rice')
                wt_im = galsim.fits.read(hdu_list=f, hdu=3, compression='rice')
        else:
            im = galsim.fits.read(hdu_list=f, hdu=1)
            if noweight:
                bp_im = wt_im = None
            else:
                bp_im = galsim.fits.read(hdu_list=f, hdu=1)
                wt_im = galsim.fits.read(hdu_list=f, hdu=2)
        #print 'im = ',im

    if not noweight:
        # The badpix image is offset by 32768 from the true value.  Subtract it off.
        if numpy.any(bp_im.array > 32767):
            bp_im -= 32768
        # Also, convert to int16, since it isn't by default weirdly.  I think this is
        # an error in astropy's RICE algorith, since fitsio converts it correctly to uint16.
        bp_im = galsim.ImageS(bp_im)

        # Also, it seems that the weight image has negative values where it should be 0.
        # Make them 0.
        wt_im.array[wt_im.array < 0] = 0.

    # Read the background image as well.
    base_file = file_name
    if os.path.splitext(base_file)[1] == '.fz':
        base_file=os.path.splitext(base_file)[0]
    if os.path.splitext(base_file)[1] == '.fits':
        base_file=os.path.splitext(base_file)[0]
    bkg_file_name = base_file + '_bkg.fits.fz'
    print('bkg_file_name = ',bkg_file_name)
    if os.path.exists(bkg_file_name):
        #bkg_im = galsim.fits.read(bkg_file_name)
        with pyfits.open(bkg_file_name) as f:
            f[1].verify('fix')
            bkg_im = galsim.fits.read(hdu_list=f, hdu=1, compression='rice')
        im -= bkg_im # Subtract off the sky background.
    else:
        cat_file_name = base_file + '_psfcat.fits'
        print(cat_file_name)
        if os.path.exists(cat_file_name):
            print('use BACKGROUND from ',cat_file_name)
            with pyfits.open(cat_file_name) as f:
                bkg = f[2].data['BACKGROUND']
            print('bkg = ',bkg)
            bkg = numpy.median(bkg)
            print('median = ',bkg)
            im -= bkg
        else:
            print('No easy way to estimate background.  Assuming image is zero subtracted...')

    stamp_size = 48

    n_psf = len(xlist)
    e1_list = [ 999. ] * n_psf
    e2_list = [ 999. ] * n_psf
    s_list = [ 999. ] * n_psf
    flag_list = [ 0 ] * n_psf
    print('len(xlist) = ',len(xlist))

    for i in range(n_psf):
        x = xlist[i]
        y = ylist[i]
        print('Measure shape for star at ',x,y)
        b = galsim.BoundsI(int(x)-stamp_size/2, int(x)+stamp_size/2, 
                           int(y)-stamp_size/2, int(y)+stamp_size/2)
        b = b & im.bounds

        try:
            subim = im[b]
            if noweight:
                subbp = subwt = None
            else:
                subbp = bp_im[b]
                subwt = wt_im[b]
            #print 'subim = ',subim.array
            #print 'subwt = ',subwt.array
            #print 'subbp = ',subbp.array
            #shape_data = subim.FindAdaptiveMom(weight=subwt, badpix=subbp, strict=False)
            shape_data = subim.FindAdaptiveMom(weight=subwt, strict=False)
        except Exception as e:
            print('Caught ',e)
            print(' *** Bad measurement (caught exception).  Mask this one.')
            flag_list[i] = MEAS_BAD_MEASUREMENT
            continue

        #print 'shape_data = ',shape_data
        #print 'image_bounds = ',shape_data.image_bounds
        #print 'shape = ',shape_data.observed_shape
        #print 'sigma = ',shape_data.moments_sigma
        #print 'amp = ',shape_data.moments_amp
        #print 'centroid = ',shape_data.moments_centroid
        #print 'rho4 = ',shape_data.moments_rho4
        #print 'niter = ',shape_data.moments_n_iter

        if shape_data.moments_status != 0:
            print('status = ',shape_data.moments_status)
            print(' *** Bad measurement.  Mask this one.')
            flag_list[i] = MEAS_BAD_MEASUREMENT
            continue

        dx = shape_data.moments_centroid.x - x
        dy = shape_data.moments_centroid.y - y
        #print 'dcentroid = ',dx,dy
        if dx**2 + dy**2 > MAX_CENTROID_SHIFT**2:
            print(' *** Centroid shifted by ',dx,dy,'.  Mask this one.')
            flag_list[i] = MEAS_CENTROID_SHIFT
            continue

        e1 = shape_data.observed_shape.e1
        e2 = shape_data.observed_shape.e2
        s = shape_data.moments_sigma
        # Note: this is (det M)^1/4, not ((Ixx+Iyy)/2)^1/2.
        # For reference, the latter is size * (1-e^2)^-1/4
        # So, not all that different, especially for stars with e ~= 0.

        # Account for the WCS:
        #print 'wcs = ',wcs
        jac = wcs.jacobian(galsim.PositionD(x,y))
        #print 'jac = ',jac
        # ( Iuu  Iuv ) = ( dudx  dudy ) ( Ixx  Ixy ) ( dudx  dvdx )
        # ( Iuv  Ivv )   ( dvdx  dvdy ) ( Ixy  Iyy ) ( dudy  dvdy )
        M = numpy.matrix( [[ 1+e1, e2 ], [ e2, 1-e1 ]] )
        #print 'M = ',M
        #print 'det(M) = ',numpy.linalg.det(M)
        M2 = jac.getMatrix() * M * jac.getMatrix().T
        #print 'M2 = ',M2
        #print 'det(M2) = ',numpy.linalg.det(M2)
        e1 = (M2[0,0] - M2[1,1]) / (M2[0,0] + M2[1,1])
        e2 = (2. * M2[0,1]) / (M2[0,0] + M2[1,1])
        #print 's = ',s
        s *= abs(numpy.linalg.det(jac.getMatrix()))**0.5
        #print 's -> ',s
        # Now convert back to a more normal shear definition, rather than distortion.
        shear = galsim.Shear(e1=e1,e2=e2)
        e1_list[i] = shear.g1
        e2_list[i] = shear.g2
        s_list[i] = s

    return e1_list,e2_list,s_list,flag_list


def measure_psf_shapes(xlist, ylist, psf_file_name, file_name, use_piff=False):
    """Given x,y positions, a psf solution file, and the wcs, measure shapes and sizes
    of the PSF model.

    We use the HSM module from GalSim to do this.

    Returns e1, e2, size, flag.
    """
    print('Read in PSFEx file: ',psf_file_name)

    n_psf = len(xlist)
    e1_list = [ 999. ] * n_psf
    e2_list = [ 999. ] * n_psf
    s_list = [ 999. ] * n_psf
    flag_list = [ 0 ] * n_psf

    try:
        if use_piff:
            psf = piff.read(psf_file_name)
        else:
            psf = galsim.des.DES_PSFEx(psf_file_name, file_name)
    except Exception as e:
        if 'CTYPE' in str(e):
            try:
                # Workaround for a bug in DES_PSFEx.  It tries to read the image file using
                # GSFitsWCS, which doesn't work if it's not a normal FITS WCS. 
                # galsim.fits.read should work correctly in those cases.
                psf = galsim.des.DES_PSFEx(psf_file_name)
                im = galsim.fits.read(file_name)
                psf.wcs = im.wcs
                e = None
            except Exception as e:
                pass
        if e is not None:
            print('Caught ',e)
            flag_list = [ PSFEX_FAILURE ] * n_psf
            return e1_list,e2_list,s_list,flag_list

    stamp_size = 64
    pixel_scale = 0.2

    im = galsim.Image(stamp_size, stamp_size, scale=pixel_scale)

    for i in range(n_psf):
        x = xlist[i]
        y = ylist[i]
        print('Measure PSFEx model shape at ',x,y)
        image_pos = galsim.PositionD(x,y)
        #print 'im_pos = ',image_pos
        if use_piff:
            im = psf.draw(x=x, y=y, image=im)
        else:
            psf_i = psf.getPSF(image_pos)
            im = psf_i.drawImage(image=im, method='no_pixel')
        #print 'im = ',im

        try:
            shape_data = im.FindAdaptiveMom(strict=False)
        except:
            print(' *** Bad measurement (caught exception).  Mask this one.')
            flag_list[i] = PSFEX_BAD_MEASUREMENT
            continue
        #print 'shape_date = ',shape_data

        if shape_data.moments_status != 0:
            print('status = ',shape_data.moments_status)
            print(' *** Bad measurement.  Mask this one.')
            flag_list[i] = PSFEX_BAD_MEASUREMENT
            continue

        dx = shape_data.moments_centroid.x - im.trueCenter().x
        dy = shape_data.moments_centroid.y - im.trueCenter().y
        #print 'centroid = ',shape_data.moments_centroid
        #print 'trueCenter = ',im.trueCenter()
        #print 'dcentroid = ',dx,dy
        if dx**2 + dy**2 > MAX_CENTROID_SHIFT**2:
            print(' *** Centroid shifted by ',dx,dy,'.  Mask this one.')
            flag_list[i] = PSFEX_CENTROID_SHIFT
            continue

        g1 = shape_data.observed_shape.g1
        g2 = shape_data.observed_shape.g2
        s = shape_data.moments_sigma * pixel_scale

        #print 'g1,g2,s = ',g1,g2,s

        e1_list[i] = g1
        e2_list[i] = g2
        s_list[i] = s

    return e1_list,e2_list,s_list,flag_list


def apply_wcs(wcs, g1, g2, s):

    scale = 2./(1.+g1*g1+g2*g2)
    e1 = g1 * scale
    e2 = g2 * scale
    I = numpy.matrix( [[ 1 + e1, e2 ], [ e2, 1 - e1 ]] ) * s*s

    J = wcs.getMatrix()
    I = J * I * J.transpose()

    e1 = (I[0,0] - I[1,1]) / (I[0,0] + I[1,1])
    e2 = (2.*I[0,1]) / (I[0,0] + I[1,1])
    s = numpy.sqrt( (I[0,0] + I[1,1]) / 2.)

    esq = e1*e1 + e2*e2
    scale = (1.-numpy.sqrt(1.-esq))/esq
    g1 = e1 * scale
    g2 = e2 * scale

    return g1, g2, s

def measure_psf_shapes_erin(xlist, ylist, psf_file_name, file_name):
    """Given x,y positions, a psf solution file, and the wcs, measure shapes and sizes
    of the PSF model.

    We use the HSM module from GalSim to do this.

    Also, this uses Erin's psfex module to render the images rather than the GalSim module.

    Returns e1, e2, size, flag.
    """
    import psfex
    print('Read in PSFEx file: ',psf_file_name)

    n_psf = len(xlist)
    e1_list = [ 999. ] * n_psf
    e2_list = [ 999. ] * n_psf
    s_list = [ 999. ] * n_psf
    flag_list = [ 0 ] * n_psf

    try:
        psf = psfex.PSFEx(psf_file_name)
    except Exception as e:
        print('Caught ',e)
        flag_list = [ PSFEX_FAILURE ] * n_psf
        return e1_list,e2_list,s_list,flag_list

    if psf._psfex is None:
        # Erin doesn't throw an exception for errors.
        # The _psfex attribute just ends up as None, so check for that.
        print('psf._psfex is None')
        flag_list = [ PSFEX_FAILURE ] * n_psf
        return e1_list,e2_list,s_list,flag_list

    wcs = galsim.fits.read(file_name).wcs

    for i in range(n_psf):
        x = xlist[i]
        y = ylist[i]
        print('Measure PSFEx model shape at ',x,y,' with Erin\'s code.')

        # Note that this code renders the image in the original coordinate system,
        # rather than in RA/Dec oriented coordinates.  So we'll need to correct for that.
        im_ar = psf.get_rec(y,x)
        local_wcs = wcs.jacobian(galsim.PositionD(x,y))
        #print 'local wcs = ',local_wcs
        #print 'pixel scale = ',numpy.sqrt(local_wcs.pixelArea())
        #print 'psf center = ',psf.get_center(y,x)
        pixel_scale= numpy.sqrt(local_wcs.pixelArea())
        im = galsim.Image(array=im_ar, scale=pixel_scale)

        try:
            shape_data = im.FindAdaptiveMom(strict=False)
        except:
            print(' *** Bad measurement (caught exception).  Mask this one.')
            flag_list[i] = PSFEX_BAD_MEASUREMENT
            continue

        if shape_data.moments_status != 0:
            print('status = ',shape_data.moments_status)
            print(' *** Bad measurement.  Mask this one.')
            flag_list[i] = PSFEX_BAD_MEASUREMENT
            continue

        cen = psf.get_center(y,x)
        true_center = galsim.PositionD( cen[1]+1, cen[0]+1 )
        dx = shape_data.moments_centroid.x - true_center.x
        dy = shape_data.moments_centroid.y - true_center.y
        #print 'centroid = ',shape_data.moments_centroid
        #print 'trueCenter = ',true_center
        #print 'dcentroid = ',dx,dy
        # Use at least 0.5 here.
        max_centroid_shift = max(MAX_CENTROID_SHIFT, 0.5)
        if dx**2 + dy**2 > max_centroid_shift**2:
            print(' *** Centroid shifted by ',dx,dy,'.  Mask this one.')
            flag_list[i] = PSFEX_CENTROID_SHIFT
            continue
        #print 'shape = ',shape_data.observed_shape
        #print 'sigma = ',shape_data.moments_sigma * pixel_scale
        g1,g2,s = apply_wcs(local_wcs, shape_data.observed_shape.g1, shape_data.observed_shape.g2,
                            shape_data.moments_sigma)
        #print 'after wcs: ',g1,g2,s

        e1_list[i] = g1
        e2_list[i] = g2
        s_list[i] = s

    return e1_list,e2_list,s_list,flag_list

def read_blacklists(tag):
    """Read the psf blacklist file and the other blacklists.

    Returns a dict indexed by the tuple (expnum, ccdnum) with the bitmask value.
    """
    d = {}  # The dict will be indexed by (expnum, ccdnum)
    print('reading blacklists')

    if False:
        # First read Eli's astrometry flags
        # cf. https://github.com/esheldon/deswl/blob/master/deswl/desmeds/genfiles.py#L498
        eli_file = '/astro/u/astrodat/data/DES/EXTRA/astrorerun/sva1_astrom_run1.0.1_stats_flagged_sheldon.fit'
        with pyfits.open(eli_file) as pyf:
            data = pyf[1].data
            for expnum, ccdnum, flag in zip(data['EXPNUM'],data['CCDNUM'],data['ASTROM_FLAG']):
                key = (int(expnum), int(ccdnum))
                d[key] = int(flag)
        print('after astrom, len(d) = ',len(d))

    # Then Alex and Steve's blacklists
    # cf. https://github.com/esheldon/deswl/blob/master/deswl/desmeds/genfiles.py#L588)
    ghost_file = '/astro/u/astrodat/data/DES/EXTRA/blacklists/ghost-scatter-y1-uniq.txt'
    streak_file = '/astro/u/astrodat/data/DES/EXTRA/blacklists/streak-y1-uniq.txt'
    noise_file = '/astro/u/astrodat/data/DES/EXTRA/blacklists/noise-y1-uniq.txt'
    with open(ghost_file) as f:
        for line in f:
            expnum, ccdnum = line.split()
            key = (int(expnum), int(ccdnum))
            if key in d:
                d[key] |= (1 << 10)
            else:
                d[key] = (1 << 10)
    with open(noise_file) as f:
        for line in f:
            expnum, ccdnum = line.split()
            key = (int(expnum), int(ccdnum))
            if key in d:
                d[key] |= (1 << 11)
            else:
                d[key] = (1 << 11)
    with open(streak_file) as f:
        for line in f:
            expnum, ccdnum = line.split()
            key = (int(expnum), int(ccdnum))
            if key in d:
                d[key] |= (1 << 13)
            else:
                d[key] = (1 << 13)
    print('after ghost, streak, len(d) = ',len(d))

    # And finally the PSFEx blacklist file.
    psf_file = '/astro/u/astrodat/data/DES/EXTRA/blacklists/psfex'
    if tag:
        psf_file += '-' + tag
    psf_file += '.txt'
    with open(psf_file) as f:
        for line in f:
            run, exp, ccdnum, flag = line.split()
            try:
                expnum = exp[6:]
                key = (int(expnum), int(ccdnum))
                flag = int(flag)
                if key in d:
                    d[key] |= (flag << 15)
                else:
                    d[key] = (flag << 15)
            except: 
                # Don't balk at bad lines in the blacklist.
                pass
    print('after psf, len(d) = ',len(d))

    return d


def main():
    import glob

    args = parse_args()

    # Make the work directory if it does not exist yet.
    work = os.path.expanduser(args.work)
    print('work dir = ',work)
    try:
        if not os.path.isdir(work):
            os.makedirs(work)
    except OSError as e:
        print("Ignore OSError from makedirs(work):")
        print(e)
        pass

    #flag_dict = read_blacklists(args.tag)

    if args.file != '':
        print('Read file ',args.file)
        with open(args.file) as fin:
            data = [ line.split() for line in fin ]
        runs, exps = list(zip(*data))
    else:
        runs = args.runs
        exps = args.exps

    # Directory to put output files.
    cat_dir = os.path.join(work,'psf_cats')
    if not os.path.exists(cat_dir):
        try:
            os.makedirs(cat_dir)
        except OSError as e:
            print('Caught %s'%e)
            if "File exists" in str(e):
                print('ignore')
            else:
                raise

    for run,exp in zip(runs,exps):

        print('Start work on run, exp = ',run,exp)
        try:
            expnum = int(exp[6:])
        except:
            expnum = 0
        print('expnum = ',expnum)

        if args.output_dir is None:
            exp_dir = os.path.join(work,exp)
        else:
            exp_dir = args.output_dir
        print('exp_dir = ',exp_dir)

        input_dir = args.input_dir
        print('input_dir = ', input_dir)

        # Get the file names in that directory.
        print('%s/%s'%(input_dir,args.exp_match))
        files = sorted(glob.glob('%s/%s'%(input_dir,args.exp_match)))

        # Setup the columns for the output catalog:
        ccdnum_col = []
        x_col = []
        y_col = []
        ra_col = []
        dec_col = []
        mag_col = []
        flag_col = []
        e1_col = []
        e2_col = []
        size_col = []
        psf_e1_col = []
        psf_e2_col = []
        psf_size_col = []

        for file_name in files:
            print('\nProcessing ', file_name)

            try:
                desdm_dir, root, ccdnum = parse_file_name(file_name)
            except:
                #print '   Unable to parse file_name %s.  Skipping this file.'%file_name
                #continue
                base_file = os.path.split(file_name)[1]
                if os.path.splitext(base_file)[1] == '.fz':
                    base_file=os.path.splitext(base_file)[0]
                root = os.path.splitext(base_file)[0]
                ccdnum = 0
                desdm_dir = None
            print('   root, ccdnum = ',root,ccdnum)
            print('   desdm_dir = ',desdm_dir)

            key = (expnum, ccdnum)
            #if key in flag_dict:
            #    black_flag = flag_dict[key]
            #    print('   blacklist flag = ',black_flag)
            #    if black_flag & (113 << 15):
            #        print('   Catastrophic flag.  Skipping this file.')
            #        if args.single_ccd:
            #            break
            #        continue
            #else:
            black_flag = 0

            # Read the star data.  From both findstars and the PSFEx used file.
            try:
                fs_data = read_findstars(exp_dir, root)
            except:
                fs_data = None
            if fs_data is None:
                print('   No _findstars.fits file found')
                if args.single_ccd:
                    break
                continue
            n_tot = len(fs_data['id'])
            n_fs = fs_data['star_flag'].sum()
            print('   n_tot = ',n_tot)
            print('   n_fs = ',n_fs)
            mask = fs_data['star_flag'] == 1

            if args.reference_tag:
                used_dir = exp_dir.replace(args.tag, args.reference_tag)
            else:
                used_dir = exp_dir
            used_data = read_used(used_dir, root, use_piff=args.use_piff)
            if used_data is None:
                print('   No .used.fits file found')
                continue
            n_used = len(used_data)
            print('   n_used = ',n_used)
            if n_used == 0:
                print('   No stars were used.')
                continue

            tot_xmin = fs_data['x'].min()
            tot_xmax = fs_data['x'].max()
            tot_ymin = fs_data['y'].min()
            tot_ymax = fs_data['y'].max()
            tot_area = (tot_xmax-tot_xmin)*(tot_ymax-tot_ymin)
            print('   bounds from sextractor = ',tot_xmin,tot_xmax,tot_ymin,tot_ymax)
            print('   area = ',tot_area)

            fs_xmin = fs_data['x'][mask].min()
            fs_xmax = fs_data['x'][mask].max()
            fs_ymin = fs_data['y'][mask].min()
            fs_ymax = fs_data['y'][mask].max()
            print('   bounds from findstars = ',fs_xmin,fs_xmax,fs_ymin,fs_ymax)
            fs_area = (fs_xmax-fs_xmin)*(fs_ymax-fs_ymin)
            print('   area = ',fs_area)

            used_xmin = used_data['X_IMAGE'].min()
            used_xmax = used_data['X_IMAGE'].max()
            used_ymin = used_data['Y_IMAGE'].min()
            used_ymax = used_data['Y_IMAGE'].max()
            print('   final bounds of used stars = ',used_xmin,used_xmax,used_ymin,used_ymax)
            used_area = (used_xmax-used_xmin)*(used_ymax-used_ymin)
            print('   area = ',used_area)
            print('   fraction used = ',float(used_area) / tot_area)

            # Figure out which fs objects go with which used objects.
            fs_index = find_fs_index(used_data, fs_data)
            used_index = find_used_index(fs_data[mask], used_data)
            print('   fs_index = ',fs_index)
            print('   used_index = ',used_index)

            # Check: This should be the same as the used bounds
            alt_used_xmin = fs_data['x'][fs_index].min()
            alt_used_xmax = fs_data['x'][fs_index].max()
            alt_used_ymin = fs_data['y'][fs_index].min()
            alt_used_ymax = fs_data['y'][fs_index].max()
            print('   bounds from findstars[fs_index] = ', end=' ')
            print(alt_used_xmin,alt_used_xmax,alt_used_ymin,alt_used_ymax)
 
            # Get the magnitude range for each catalog.
            tot_magmin = fs_data['mag'].min()
            tot_magmax = fs_data['mag'].max()
            print('   magnitude range of full catalog = ',tot_magmin,tot_magmax)
            fs_magmin = fs_data['mag'][mask].min()
            fs_magmax = fs_data['mag'][mask].max()
            print('   magnitude range of fs stars = ',fs_magmin,fs_magmax)
            used_magmin = fs_data['mag'][fs_index].min()
            used_magmax = fs_data['mag'][fs_index].max()
            print('   magnitude range of used stars = ',used_magmin,used_magmax)

            try:
                # Get the wcs from the image file
                wcs = get_wcs(file_name)

                # Measure the shpes and sizes of the stars used by PSFEx.
                x = fs_data['x'][mask]
                y = fs_data['y'][mask]
                mag = fs_data['mag'][mask]
                e1, e2, size, meas_flag = measure_shapes(x, y, file_name, wcs, args.noweight)
                # Measure the model shapes, sizes.
                psf_file_name = os.path.join(exp_dir, root + '_psfcat.psf')
                psf_e1, psf_e2, psf_size, psf_flag = measure_psf_shapes(
                        x, y, psf_file_name, file_name, use_piff=args.use_piff)
            except Exception as e:
                print('Catastrophic error trying to measure the shapes:')
                print(e)
                print('Skip this file')
                raise e
                continue

            # Put all the flags together:
            flag = numpy.array([ m | p for m,p in zip(meas_flag,psf_flag) ])
            print('meas_flag = ',meas_flag)
            print('psf_flag = ',psf_flag)
            print('flag = ',flag)

            # Add in flags for bad indices
            bad_index = numpy.where(used_index < 0)[0]
            print('bad_index = ',bad_index)
            flag[bad_index] |= NOT_USED
            print('flag => ',flag)

            # Add in flags for reserved stars
            reserve_data = read_reserve(exp_dir, root)
            if reserve_data is None:
                print('   No _reserve.fits file found')
            else:
                n_reserve = len(reserve_data)
                print('   n_reserve = ',n_reserve)

                # Figure out which fs objects go with which reserved objects.
                fs2_index = find_fs_index(reserve_data, fs_data, suffix='WIN_IMAGE')
                res_index = find_used_index(fs_data[mask], reserve_data, suffix='WIN_IMAGE')
                print('   fs2_index = ',fs2_index)
                print('   res_index = ',res_index)

                res_index = numpy.where(res_index >= 0)[0]
                print('res_index = ',res_index)
                flag[res_index] |= RESERVED
                print('flag => ',flag)

            # If the ccd is blacklisted, everything gets the blacklist flag
            if black_flag:
                print('black_flag = ',black_flag)
                print('type(black_flag) = ',type(black_flag))
                print('type(flag[0]) = ',type(flag[0]))
                print('type(flag[0] | black_flag) = ',type(flag[0] | black_flag))
                black_flag *= BLACK_FLAG_FACTOR
                print('black_flag => ',black_flag)
                flag |= black_flag
                print('flag => ',flag)

            # Compute ra,dec from the wcs:
            coord = [ wcs.toWorld(galsim.PositionD(xx,yy)) for xx,yy in zip(x,y) ]
            try:
                ra = [ c.ra / galsim.degrees for c in coord ]
                dec = [ c.dec / galsim.degrees for c in coord ]
            except:
                # Sims may be using simple WCS with no ra, dec.  Just take coord.x,y instead
                ra = [ c.x * galsim.arcsec / galsim.degrees for c in coord]
                dec = [ c.y * galsim.arcsec / galsim.degrees for c in coord]

            # Extend the column arrays with this chip's data.
            ccdnum_col.extend([ccdnum] * n_fs)
            x_col.extend(x)
            y_col.extend(y)
            ra_col.extend(ra)
            dec_col.extend(dec)
            mag_col.extend(mag)
            flag_col.extend(flag)
            e1_col.extend(e1)
            e2_col.extend(e2)
            size_col.extend(size)
            psf_e1_col.extend(psf_e1)
            psf_e2_col.extend(psf_e2)
            psf_size_col.extend(psf_size)
            assert len(ccdnum_col) == len(x_col)
            assert len(ccdnum_col) == len(y_col)
            assert len(ccdnum_col) == len(ra_col)
            assert len(ccdnum_col) == len(dec_col)
            assert len(ccdnum_col) == len(mag_col)
            assert len(ccdnum_col) == len(flag_col)
            assert len(ccdnum_col) == len(e1_col)
            assert len(ccdnum_col) == len(e2_col)
            assert len(ccdnum_col) == len(size_col)
            assert len(ccdnum_col) == len(psf_e1_col)
            assert len(ccdnum_col) == len(psf_e2_col)
            assert len(ccdnum_col) == len(psf_size_col)

            cols = pyfits.ColDefs([
                pyfits.Column(name='ccdnum', format='I', array=[ccdnum] * n_fs),
                pyfits.Column(name='x', format='E', array=x),
                pyfits.Column(name='y', format='E', array=y),
                pyfits.Column(name='ra', format='E', array=ra),
                pyfits.Column(name='dec', format='E', array=dec),
                pyfits.Column(name='mag', format='E', array=mag),
                pyfits.Column(name='flag', format='J', array=flag),
                pyfits.Column(name='e1', format='E', array=e1),
                pyfits.Column(name='e2', format='E', array=e2),
                pyfits.Column(name='size', format='E', array=size),
                pyfits.Column(name='psf_e1', format='E', array=psf_e1),
                pyfits.Column(name='psf_e2', format='E', array=psf_e2),
                pyfits.Column(name='psf_size', format='E', array=psf_size),
                ])

            # Depending on the version of pyfits, one of these should work:
            try:
                tbhdu = pyfits.BinTableHDU.from_columns(cols)
            except:
                tbhdu = pyfits.new_table(cols)
            cat_file = os.path.join(cat_dir, root + "_psf.fits")
            tbhdu.writeto(cat_file, clobber=True)
            print('wrote cat_file = ',cat_file)

            if args.single_ccd:
                break


        cols = pyfits.ColDefs([
            pyfits.Column(name='ccdnum', format='I', array=ccdnum_col),
            pyfits.Column(name='x', format='E', array=x_col),
            pyfits.Column(name='y', format='E', array=y_col),
            pyfits.Column(name='ra', format='E', array=ra_col),
            pyfits.Column(name='dec', format='E', array=dec_col),
            pyfits.Column(name='mag', format='E', array=mag_col),
            pyfits.Column(name='flag', format='J', array=flag_col),
            pyfits.Column(name='e1', format='E', array=e1_col),
            pyfits.Column(name='e2', format='E', array=e2_col),
            pyfits.Column(name='size', format='E', array=size_col),
            pyfits.Column(name='psf_e1', format='E', array=psf_e1_col),
            pyfits.Column(name='psf_e2', format='E', array=psf_e2_col),
            pyfits.Column(name='psf_size', format='E', array=psf_size_col),
            ])

        # Depending on the version of pyfits, one of these should work:
        try:
            tbhdu = pyfits.BinTableHDU.from_columns(cols)
        except:
            tbhdu = pyfits.new_table(cols)
        if '_' in root:
            exp_root = root.rsplit('_',1)[0]
        else:
            exp_root = root
        print('exp_root = ',exp_root)
        cat_file = os.path.join(cat_dir, exp_root + "_exppsf.fits")
        tbhdu.writeto(cat_file, clobber=True)
        print('wrote cat_file = ',cat_file)

    print('\nFinished processing all exposures')


if __name__ == "__main__":
    main()
