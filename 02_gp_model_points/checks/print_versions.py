"""Print the Python and package versions of the active environment.

Used to record the versions behind requirements_gp.txt. For each package it
prints the version and the folder it was imported from (conda/module install
or user site-packages in ~/.local).

Inputs:  none.
Outputs: text on stdout.
Environment: any Python 3 environment.
Run:     python checks/print_versions.py   (inside a job, see checks/sbatch_checks.sh)
Original: new helper script (no original).
"""
import importlib
import sys

# ---- paths and settings ------------------------------------------------------
PACKAGES = ['numpy', 'scipy', 'pandas', 'xarray', 'netCDF4', 'h5netcdf', 'sklearn',
            'joblib', 'GPy', 'paramz', 'matplotlib', 'geopandas', 'pyproj', 'shapely']

print('python', sys.version.replace('\n', ' '))
print('executable', sys.executable)
for name in PACKAGES:
    try:
        mod = importlib.import_module(name)
        print(f'{name:12s} {getattr(mod, "__version__", "?"):12s} {mod.__file__}')
    except Exception as err:  # package missing in this environment
        print(f'{name:12s} not available ({type(err).__name__})')
try:
    import pyproj
    print('PROJ (pyproj.proj_version_str)', pyproj.proj_version_str)
except Exception:
    pass
try:
    import xarray as xr
    print('xarray backends', list(xr.backends.list_engines()))
except Exception:
    pass
