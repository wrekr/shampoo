"""
Translation from IDL via source code: https://github.com/davidgrier/lorenzmie
"""

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import numpy as np
from numba import jit

__all__ = ['lorenz_mie_field_cartesian_suppressed',
           'lorenz_mie_field_cartesian']

COMPLEX_DTYPE = np.complex128


@jit(nopython=True)
def dcomplex(a, b=0):
    """
    Construct a complex number (or array) with the same call signature
    as the IDL ``dcomplex`` constructor.

    Parameters
    ----------
    a : float or `~numpy.ndarray`
        Real part of a complex number
    b : float or `~numpy.ndarray`
        Imaginary part of a complex number

    Returns
    -------
    A complex number or array of complex numbers.
    """
    return COMPLEX_DTYPE(a + 1j * b)


@jit(nopython=True)
def dcomplexarr(n):
    """
    Construct a complex 1D array with the same call signature
    as the IDL ``dcomplexarr`` constructor.

    Parameters
    ----------
    n : int
        Length of complex array along first axis

    Returns
    -------
    A complex array.
    """
    return np.zeros(n, dtype=COMPLEX_DTYPE)


@jit(nopython=True)
def dcomplexarr2d(n, m):
    """
    Construct a complex 2D array with the same call signature
    as the IDL ``dcomplexarr`` constructor.

    Parameters
    ----------
    n : int
        Length of complex array along first axis
    m : int (optional)
        Length of complex array along second axis. If ``m`` is `None`, return
        only a one dimensional array

    Returns
    -------
    A complex array.
    """
    return np.zeros((n, m), dtype=COMPLEX_DTYPE)


@jit(nopython=True)
def meshgrid(xrange, yrange):
    """
    Replacement for `~numpy.meshgrid` that gets compiled by Numba.
    """
    x = np.zeros((yrange.shape[0], xrange.shape[0]))
    y = np.zeros((yrange.shape[0], xrange.shape[0]))

    for i in range(x.shape[0]):
        x[i, :] = xrange

    for i in range(y.shape[1]):
        y[:, i] = yrange

    return x, y


@jit(nopython=True)
def lorenz_mie_field_spherical(rp, ap, n_sphere, nm, lambda_, mpp, dim, alpha=1,
                               delta=0):
    """
    Calculate the field produced by Lorenz-Mie scattering from a sphere.

    Parameters
    ----------
    rp  : `~numpy.ndarray`
        [x,y,z] position of sphere
    ap  : float
        radius of sphere [micrometers]
    n_sphere  : complex
        refractive index of sphere
    nm  : complex
        refractive index of medium
    lambda_ : float
        vacuum wavelength of light [micrometers]
    mpp: float
        micrometers per pixel
    dim : list
        [nx,ny] dimensions of image [pixels]

    alpha: float
        fraction of incident light scattered by particle. Default: 1.

    Returns
    -------
    field : `~numpy.ndarray`
        Field before being reshaped into the hologram coordinates
    """
    nx = float(dim[0])
    ny = float(dim[1])

    xrange = np.arange(nx) - np.float64(rp[0])
    yrange = np.arange(ny) - np.float64(rp[1])
    x, y = meshgrid(xrange, yrange)

    zp = np.float64(rp[2])

    field = spherefield(x, y, zp, ap, n_sphere, nm, lambda_, mpp)

    # BM: copied to this function from spherefield
    lambda_m = lambda_ / nm.real / mpp  ## medium wavenp.sizegth [pixel]
    k = 2 * np.pi / lambda_m

    field *= alpha * np.exp(-k * (zp + delta) * 1j)  ## scattered field
    field[0, :] += 1.  ## incident field
    return field * np.conj(field)


def lorenz_mie_field_cartesian(rp, ap, n_sphere, nm, lambda_, mpp, dim, alpha=1,
                               delta=0):
    """
    Calculate the field produced by Lorenz-Mie scattering from a sphere.

    Parameters
    ----------
    rp  : `~numpy.ndarray`
        [x,y,z] position of sphere
    ap  : float
        radius of sphere [micrometers]
    n_sphere  : complex
        refractive index of sphere
    nm  : complex
        refractive index of medium
    lambda_ : float
        vacuum wavelength of light [micrometers]
    mpp: float
        micrometers per pixel
    dim : list
        [nx,ny] dimensions of image [pixels]

    alpha: float
        fraction of incident light scattered by particle. Default: 1.

    Returns
    -------
    field : `~numpy.ndarray`
        Observed field in the same shape as the hologram
    """
    field = lorenz_mie_field_spherical(rp, ap, n_sphere, nm, lambda_, mpp, dim,
                                       alpha=alpha, delta=delta)
    a = np.sum(field.real, 0)
    nx = float(dim[0])
    ny = float(dim[1])
    return a.reshape((int(nx), int(ny)))


@jit(nopython=True)
def gaussian_kernel(x, y, sigma):
    """
    Given ``x``, ``y`` from meshgrid and a Gaussian width ``sigma``, calculate
    the Gaussian's amplitude on the (x, y) grid.

    Parameters
    ----------
    x : `~numpy.ndarray`
    y : `~numpy.ndarray`
    sigma : float

    Returns
    -------
    g : `~numpy.ndarray`
        2D Gaussian
    """
    return np.exp(-(x ** 2 + y ** 2) / 2 / sigma ** 2)


@jit(nopython=True)
def suppress_hologram(rp, holo, kernel_radius):
    """
    Suppress the hologram intensity with distance from the particle centroid.

    Parameters
    ----------
    rp : `~numpy.ndarray`
        [x, y, z] coordinates of the sphere
    holo : `~numpy.ndarray`
        Hologram to suppress

    Results
    -------
    suppressed : `~numpy.ndarray`
        Suppressed hologram.
    """
    x0 = rp[0]
    y0 = rp[1]
    suppressed = holo.copy() - np.median(holo)
    x_range = np.arange(suppressed.shape[0]) - np.float64(x0)
    y_range = np.arange(suppressed.shape[1]) - np.float64(y0)
    x, y = meshgrid(x_range, y_range)
    # gauss = gaussian_kernel(x, y, kernel_radius)
    # suppressed *= gauss
    r = np.sqrt(x ** 2 + y ** 2)
    suppressed *= np.exp(-r / 20) + 0.05
    return suppressed


def lorenz_mie_field_cartesian_suppressed(rp, ap, n_sphere, nm, lambda_, mpp,
                                          dim, alpha=1, delta=0,
                                          kernel_radius=15):
    """
    Calculate the field produced by Lorenz-Mie scattering from a sphere,
    suppressed with distance from the centroid.

    Parameters
    ----------
    rp  : `~numpy.ndarray`
        [x,y,z] position of sphere
    ap  : float
        radius of sphere [micrometers]
    n_sphere  : complex
        refractive index of sphere
    nm  : complex
        refractive index of medium
    lambda_ : float
        vacuum wavelength of light [micrometers]
    mpp: float
        micrometers per pixel
    dim : list
        [nx,ny] dimensions of image [pixels]

    alpha: float
        fraction of incident light scattered by particle. Default: 1.

    Returns
    -------
    field : `~numpy.ndarray`
        Observed field in the same shape as the hologram
    """
    holo = lorenz_mie_field_cartesian(rp, ap, n_sphere, nm, lambda_, mpp, dim,
                                      alpha=alpha, delta=delta)
    suppressed_hologram = suppress_hologram(rp, holo, kernel_radius)
    return suppressed_hologram


@jit(nopython=True)
def spherefield(x, y, z, a, n_sphere, nm, lambda_, mpp):
    """
    x: [npts] array of pixel coordinates [pixels]
    y: [npts] array of pixel coordinates [pixels]
    z: If field is required in a single plane, then
       z is the plane's distance from the sphere's center.
       Otherwise, z is an [npts] array of coordinates.

       NOTE: Ideally, x, y and z should be double precision.
             This is left to the calling program for efficiency.

    ap: radius of sphere [micrometers]
    n_sphere: Complex refractive index of sphere
    nm: Complex refractive index of medium.
    lambda: vacuum wavenp.sizegth of light [micrometers]
    mpp: microns per pixel.
    """
    ab = sphere_coefficients(a, n_sphere, nm, lambda_)
    lambda_m = lambda_ / nm.real / mpp  ## medium wavenp.sizegth [pixel]

    field = sphericalfield(x, y, z, ab, lambda_m)  # , cartesian=cartesian)

    return field


@jit(nopython=True)
def sphericalfield(x_, y_, z_, ab, lambda_):
    """
    x : [npts] array of pixel coordinates [pixels]
    y : [npts] array of pixel coordinates [pixels]
    z : If field is required in a single plane, then z is the plane's
       distance from the sphere's center [pixels].
       Otherwise, z is an [npts] array of coordinates.

    NOTE: Ideally, x, y and z should be double precision.
          This is left to the calling program for efficiency.

    ab : [2,nc] array of Lorenz-Mie scattering coefficients, where
          nc is the number of terms required for convergence.

    lambda : wavelenth of light in medium [pixels]
    """
    npts = x_.shape[0] * x_.shape[1]
    nc = ab[0, :].shape[0] - 1  # number of terms required for convergence

    k = 2 * np.pi / lambda_  # wavenumber in medium [pixel**-1]

    ci = dcomplex(0, 1)

    # convert to spherical coordinates centered on the sphere.
    # (r, theta, phi) is the spherical coordinate of the pixel
    # at (x,y) in the imaging plane at distance z from the
    # center of the sphere.
    rho = np.sqrt(x_ ** 2 + y_ ** 2)
    r = np.sqrt(rho ** 2 + z_ ** 2)
    theta = np.arctan2(rho, z_)
    phi = np.arctan2(y_, x_)
    costheta = np.cos(theta).ravel()
    sintheta = np.sin(theta).ravel()
    cosphi = np.cos(phi).ravel()
    sinphi = np.sin(phi).ravel()

    kr = k * r.ravel()  # reduced radial coordinate

    # starting points for recursive function evaluation ...
    # ... Riccati-Bessel radial functions, page 478
    sinkr = np.sin(kr)
    coskr = np.cos(kr)

    xi_nm2 = coskr + 1j * sinkr  # \xi_{-1}(kr)
    xi_nm1 = sinkr - 1j * coskr  # \xi_0(kr)

    # ... angular functions (4.47), page 95
    pi_nm1 = 0 + np.zeros(npts, dtype=np.float64)  # \pi_0(\cos\theta)
    pi_n = 1 + np.zeros(npts, dtype=np.float64)  # \pi_1(\cos\theta)

    # storage for vector spherical harmonics: [r,theta,phi]
    Mo1n = dcomplexarr2d(3, npts)
    Ne1n = dcomplexarr2d(3, npts)

    # storage for scattered field
    Es = dcomplexarr2d(3, npts)

    # Compute field by summing multipole contributions
    for n in range(1, nc):
        # upward recurrences ...
        # ... Legendre factor (4.47)
        # Method described by Wiscombe (1980)
        swisc = pi_n * costheta
        twisc = swisc - pi_nm1
        tau_n = pi_nm1 - n * twisc  # -\tau_n(\cos\theta)

        # ... Riccati-Bessel function, page 478
        xi_n = (2 * n - 1) * xi_nm1 / kr - xi_nm2  # \xi_n(kr)

        # vector spherical harmonics (4.50)
        Mo1n[1, :] = pi_n * xi_n  # ... divided by cosphi/kr
        Mo1n[2, :] = tau_n * xi_n  # ... divided by sinphi/kr

        dn = (n * xi_n) / kr - xi_nm1
        Ne1n[0, :] = n * (n + 1) * pi_n * xi_n  # ... divided by cosphi sintheta/kr**2
        Ne1n[1, :] = tau_n * dn  # ... divided by cosphi/kr
        Ne1n[2, :] = pi_n * dn  # ... divided by sinphi/kr

        # prefactor, page 93
        En = ci ** n * (2 * n + 1) / n / (n + 1)
        # the scattered field in spherical coordinates (4.45)

        Es += (En * ci * ab[0, n]) * Ne1n - (En * ab[1, n]) * Mo1n

        # upward recurrences ...
        # ... angular functions (4.47)
        # Method described by Wiscombe (1980)
        pi_nm1 = pi_n
        pi_n = swisc + ((n + 1) / n) * twisc

        # ... Riccati-Bessel function
        xi_nm2 = xi_nm1
        xi_nm1 = xi_n

    # geometric factors were divided out of the vector
    # spherical harmonics for accuracy and efficiency ...
    # ... put them back at the end.
    Es[0, :] *= cosphi * sintheta / kr ** 2
    Es[1, :] *= cosphi / kr
    Es[2, :] *= sinphi / kr
    # in IDL version by default the scattered wave is returned in spherical
    # coordinates.  Project components onto Cartesian coordinates.
    # Assumes that the incident wave propagates along z and
    # is linearly polarized along x

    # In python version, do cartesian always
    Ec = Es.copy()
    Ec[0, :] = Es[0, :] * sintheta * cosphi + Es[1, :] * costheta * cosphi - Es[2, :] * sinphi
    Ec[1, :] = Es[0, :] * sintheta * sinphi + Es[1, :] * costheta * sinphi + Es[2, :] * cosphi
    Ec[2, :] = Es[0, :] * costheta - Es[1, :] * sintheta

    return Ec


@jit(nopython=True)
def Nstop(x, m):
    """
    Number of terms to keep in the partial wave expansion
    """
    # ;; Wiscombe (1980)
    xl = x  # [-1]
    if xl < 8.:
        ns = np.floor(xl + 4. * xl ** (1. / 3.) + 1.)
    elif xl < 4200.:
        ns = np.floor(xl + 4.05 * xl ** (1. / 3.) + 2.)
    elif xl > 4199.:
        ns = np.floor(xl + 4. * xl ** (1. / 3.) + 2.)

    # ;; Yang (2003) Eq. (30)
    a = np.array([ns, abs(x * m)])
    return int(np.floor(np.max(a)) + 15)


@jit(nopython=True)
def shift(a, steps):
    """
    Replacement for `~numpy.roll`
    """
    b = np.zeros_like(a, dtype=COMPLEX_DTYPE)
    len_a = a.shape[0]
    for i in range(len_a):
        if i >= steps:
            b[i] = a[i - steps]
        if i < steps:
            offset = b.shape[0] - steps
            b[i] = a[i + offset]
    return b


@jit(nopython=True)
def sphere_coefficients(ap, n_sphere, nm, lambda_):
    """
    ap : [nlayers] radii of layered sphere [micrometers]
        NOTE: ap and np are reordered automatically so that
        ap is in ascending order.

    n_sphere : [nlayers] (complex) refractive indexes of sphere's layers

    nm : (complex) refractive index of medium

    lambda_ : wavelength of light [micrometers]
    """
    nlayers = 1  # np.size(ap)

    x = 2 * np.pi * nm.real * ap / lambda_  # size parameter [array]
    m = dcomplex(n_sphere / nm)  # relative refractive index [array]
    nmax = Nstop(x, m)  # number of terms in partial-wave expansion
    ci = dcomplex(0, 1)  # imaginary unit

    # arrays for storing results
    ab = dcomplexarr2d(2, nmax + 1)

    D1 = dcomplexarr(nmax + 2)
    D1_a = dcomplexarr2d(nlayers, nmax + 2)

    D3 = dcomplexarr(nmax + 1)
    D3_a = dcomplexarr2d(nlayers, nmax + 1)

    Psi = dcomplexarr(nmax + 1)
    Zeta = dcomplexarr(nmax + 1)
    PsiZeta = dcomplexarr(nmax + 1)
    PsiZeta_a = dcomplexarr2d(nlayers, nmax + 1)

    Ha = dcomplexarr2d(nlayers, nmax + 1)
    Hb = dcomplexarr2d(nlayers, nmax + 1)

    # Calculate D1, D3 and PsiZeta for Z1 in the first layer
    z1 = x * m
    for n in list(range(1, nmax + 1))[::-1]:
        D1_a[0, n - 1] = np.float64(n) / z1 - 1.0 / (D1_a[0, n] + np.float64(n) / z1)

    PsiZeta_a[0, 0] = 0.5 * (1 - np.exp(2 * ci * z1))  # Eq. (18a)

    D3_a[0, 0] = ci  # Eq. (18a)

    # Ha and Hb in the core
    Ha[0, :] = D1_a[0, :-1]  # Eq. (7a)
    Hb[0, :] = D1_a[0, :-1]  # Eq. (8a)

    z1 = dcomplex(x)
    # Downward recurrence for D1, Eqs. (16a) and (16b)
    for n in list(range(1, nmax))[::-1]:  # Eq. (16b)
        D1[n - 1] = np.float64(n) / z1 - (1.0 / (D1[n] + np.float64(n) / z1))

    # Upward recurrence for Psi, Zeta, PsiZeta and D3, Eqs. (18a) and (18b)
    Psi[0] = np.sin(z1)  # Eq. (18a)
    Zeta[0] = -ci * np.exp(ci * z1)
    PsiZeta[0] = 0.5 * (1.0 - np.exp(2.0 * ci * z1))
    D3[0] = ci
    for n in range(1, nmax):  # Eq. (18b)
        Psi[n] = Psi[n - 1] * (np.float64(n) / z1 - D1[n - 1])
        Zeta[n] = Zeta[n - 1] * (np.float64(n) / z1 - D3[n - 1])
        PsiZeta[n] = PsiZeta[n - 1] * (np.float64(n) / z1 - D1[n - 1]) * (np.float64(n) / z1 - D3[n - 1])
        D3[n] = D1[n] + ci / PsiZeta[n]

    shift_Psi = shift(Psi, 1)
    shift_Zeta = shift(Zeta, 1)

    n2 = np.arange(nmax + 1)
    for n in range(ab.shape[1]):

        ab[0, n]  = (((Ha[0, n]/m + np.float64(n2[n])/x) * Psi[n]  - shift_Psi[n]) /
                     ((Ha[0, n]/m + np.float64(n2[n])/x) * Zeta[n] - shift_Zeta[n])) # Eq. (5)

        ab[1, n]  = (((Hb[0, n]*m + np.float64(n2[n])/x) * Psi[n]  - shift_Psi[n]) /
                     ((Hb[0, n]*m + np.float64(n2[n])/x) * Zeta[n] - shift_Zeta[n])) # Eq. (6)

    ab[:, 0] = dcomplex(0)

    return ab