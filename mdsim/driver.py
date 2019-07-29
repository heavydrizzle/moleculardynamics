# -*- coding: utf-8 -*-
"""Created on Tue Jun 25 14:12:58 2019

@author: Efren A. Serra
"""

import math, numpy as np, re, sys

from _globals import NDIM, _mdsim_globals, _namelist_converter
from _types   import (
        Mol, Prop, VecR
        )

from _functions import (
        leapfrog_update_coordinates, \
        leapfrog_update_velocities, \
        )

from _vfunctions import (
        rv_add, \
        rv_dot, \
        rv_rand, \
        rv_scale, \
        rv_sadd, \
        ra_zero, \
        vecr_div, \
        vecr_dot, \
        vecr_mul, \
        vecr_sadd, \
        vecr_wrap, \
        )

def AccumProps(icode: int):
    """Accumulate thermodynamics properties.
    Parameters
    ----------
    icount : int,
    """
    if icode == 0:
        _mdsim_globals['totEnergy'].zero()
        _mdsim_globals['kinEnergy'].zero()
        _mdsim_globals['pressure'].zero()
    elif icode == 1:
        _mdsim_globals['totEnergy'].accum()
        _mdsim_globals['kinEnergy'].accum()
        _mdsim_globals['pressure'].accum()        
    elif icode == 2:
        stepAvg = _mdsim_globals['stepAvg']
        _mdsim_globals['totEnergy'].avg(stepAvg)
        _mdsim_globals['kinEnergy'].avg(stepAvg)
        _mdsim_globals['pressure'].avg(stepAvg)

def AllocArrays():
    """Allocate molecular array.
    """
    nMol = _mdsim_globals['nMol']
    # the molecules
    mol = \
    np.array([Mol() for i in range(nMol)], dtype=Mol)
    _mdsim_globals['mol'] = mol[np.newaxis, :]

def ApplyBoundaryCond():
    """Apply periodic boundary conditions.
    """
    mol    = _mdsim_globals['mol']
    region = _mdsim_globals['region']

    for i, m in enumerate(mol[0,:]):
        m.r_wrap(region)

def ComputeForces():
    """Compute the MD forces by evaluating the LJ potential
    """
    j1 : int = 0
    j2 : int = 0
    fcVal : float = 0.
    rr : np.float64 = 0.
    rrCut : float = 0.
    rri : float   = 0.
    rri3 : float  = 0.

    mol    = _mdsim_globals['mol']
    nMol   = _mdsim_globals['nMol']
    region = _mdsim_globals['region']
    rrCut  = math.sqrt(_mdsim_globals['rCut'])

    for m in mol[0,:]:
        m.ra_zero()

    _mdsim_globals['uSum'] = 0.
    _mdsim_globals['virSum'] = 0.

    # compute cross differences
    _mdsim_globals['uSum'] = 0.
    for j1 in range(nMol-1):
        a = mol[0, j1]
        for j2 in range(j1+1, nMol):
            b = mol[0, j2]
            dr = a.r_diff(b)
            dr = vecr_wrap(dr, region)
            rr = vecr_dot(dr, dr)
            if rr < rrCut:
                rri = 1. / rr
                rri3 = rri ** 3
                fcVal = 48.0 * rri3 * (rri3 - 0.5) * rri
                # molecule at: j1
                a.ra.x += fcVal * dr.x
                a.ra.y += fcVal * dr.y
                # molecule at: j2
                b.ra.x += -1.0 * fcVal * dr.x
                b.ra.y += -1.0 * fcVal * dr.y
                _mdsim_globals['uSum'] += 4. * rri3 * (rri3 - 1.) + 1.
                _mdsim_globals['virSum'] += fcVal * rr

def EvalProps():
    """Evaluate thermodynamic properties
    """
    density  = _mdsim_globals['density']
    mol  = _mdsim_globals['mol']
    nMol = _mdsim_globals['nMol']
    uSum = _mdsim_globals['uSum']
    virSum = _mdsim_globals['virSum']

    vSum = VecR()
    vvSum : float = 0.
    for m in mol[0, :]:
        rv_add(vSum, m)
        vvSum += rv_dot(m, m)

    _mdsim_globals['vSum'] = vSum
    _mdsim_globals['kinEnergy'].val = 0.5 * vvSum / nMol
    _mdsim_globals['totEnergy'].val = \
    _mdsim_globals['kinEnergy'].val + uSum / nMol
    _mdsim_globals['pressure'].val = density * (vvSum + virSum) / (nMol * NDIM)

def GetNameList(fd: str):
    """
    Parameters
    ----------
    fd : str, the filename
    """
    with open(fd, 'r') as f:
        pattern = re.compile(r'initUcell')
        for line in f:
            m = pattern.match(line)
            if m:
                k = 'initUcell'
                line = line[len(k):]
                (nx,ny) = line.split()
                # matrix of molecular unit cells
                _mdsim_globals[k] = \
                _namelist_converter[k](nx,ny)
            else:
                (k,v) = line.split()
                _mdsim_globals[k] = \
                _namelist_converter[k](v)

def LeapfrogStep(part: int):
    """
    Parameters
    ----------
    part : int, 
    """
    deltaT : float = _mdsim_globals['deltaT']
    mol            = _mdsim_globals['mol']

    if part == 1:
        for i, m in enumerate(mol[0, :]):
            # integrate velocities
            m.update_velocities(leapfrog_update_velocities, 0.5 * deltaT)

            # integrate coordinates
            m.update_coordinates(leapfrog_update_coordinates, deltaT)
    else:
        for i, m in enumerate(mol[0, :]):
            # integrate velocities
            m.update_velocities(leapfrog_update_velocities, 0.5 * deltaT)

def PrintNameList(fd: object):
    """
    Parameters
    ----------
    fd : object, 
    """
    print(_mdsim_globals, file=fd)

def PrintSummary(fd: object):
    """
    Parameters
    ----------
    fd : object, 
    """
    nMol = _mdsim_globals['nMol']
    totEnergy='%7.4f %7.4f'%_mdsim_globals['totEnergy'].est()
    kinEnergy='%7.4f %7.4f'%_mdsim_globals['kinEnergy'].est()
    pressure='%7.4f'%_mdsim_globals['pressure'].est()[0]
    print("%5d %8.4f %7.4f %s %s %s"%(\
          _mdsim_globals['stepCount'],\
          _mdsim_globals['timeNow'],  \
          _mdsim_globals['vSum'].vcsum() / nMol,\
          totEnergy, \
          kinEnergy, \
          pressure),  \
          file=fd)

def InitCoords():
    """Initialize the molecular coordinates
    """
    mol = _mdsim_globals['mol']
    region = _mdsim_globals['region']
    initUcell = _mdsim_globals['initUcell']

    gap = vecr_div(region, initUcell)
    for nx in range(initUcell.x):
        for ny in range(initUcell.y):
            c = VecR(x=nx + 0.5, y=ny + 0.5)
            c = vecr_mul(c, gap)
            c = vecr_sadd(c, -0.5, region)
            mol[0, nx * initUcell.x + ny].r = c

def InitVels():
    """Initialize the molecular velocities
    """
    mol    = _mdsim_globals['mol']
    nMol   = _mdsim_globals['nMol']
    velMag = _mdsim_globals['velMag']

    vSum = VecR(x=0., y=0.)
    for m in mol[0, :]:
        m.rv = VecR()
        rv_rand(m)
        rv_scale(m, velMag)
        rv_add(vSum, m)

    _mdsim_globals['vSum'] = vSum
    # scale molecular velocities
    for m in mol[0, :]:
        rv_sadd(m, -1. / nMol, vSum)

def InitAccels():
    """Initialize the molecular accelerations
    """
    mol = _mdsim_globals['mol']
    for m in mol[0, :]:
        m.ra = VecR()
        ra_zero(m)

def SetupJob():
    """Setup global variables prior to simulation.
    """
    AllocArrays()
    _mdsim_globals['stepCount'] = 0
    InitCoords()
    InitVels()
    InitAccels()
    AccumProps(0)

def SetParams():
    density = _mdsim_globals['density']
    initUcell = _mdsim_globals['initUcell']

    _mdsim_globals['rCut'] = math.pow(2.,1./6.)
    _mdsim_globals['region'] = \
    VecR(x=1. / math.sqrt(density) * initUcell.x, \
         y=1. / math.sqrt(density) * initUcell.y)

    # the total number of molecules
    nMol = initUcell.x * initUcell.y
    _mdsim_globals['nMol'] = nMol
    _mdsim_globals['velMag'] = \
    math.sqrt(NDIM * (1. - 1. / nMol) * _mdsim_globals['temperature'])

    # initialize kinEnery, pressure and totEnergy properties
    _mdsim_globals['kinEnergy'] = Prop()
    _mdsim_globals['pressure']  = Prop()
    _mdsim_globals['totEnergy'] = Prop()

def SingleStep():
    _mdsim_globals['stepCount'] += 1
    _mdsim_globals['timeNow'] = \
    _mdsim_globals['stepCount'] * _mdsim_globals['deltaT']
    LeapfrogStep(1)
    ApplyBoundaryCond()
    ComputeForces()
    LeapfrogStep(2)
    EvalProps()
    AccumProps(1)
    if _mdsim_globals['stepCount'] % _mdsim_globals['stepAvg'] == 0:
        AccumProps(2)
        PrintSummary(sys.stdout)
        AccumProps(0)

def RunMDSim(argv: list):
    GetNameList(argv[1])
    PrintNameList(sys.stdout)
    SetParams()
    SetupJob()
    moreCycles = True
    while moreCycles:
        SingleStep()
        if _mdsim_globals['stepCount'] >= _mdsim_globals['stepLimit']:
            moreCycles = False

if __name__ == "__main__":
    RunMDSim(['driver.py', 'pr_02_01.in'])