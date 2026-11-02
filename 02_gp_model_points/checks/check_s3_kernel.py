"""Compare lnscale_-1.npy and var_-1.npy written by s3_save_kernel.py with the originals.

Inputs:  folder with the original files; folder with the new files.
Outputs: text on stdout (exact equality and maximum absolute difference).
Environment: any Python with numpy.
Run:     python checks/check_s3_kernel.py <original iter dir> <new iter dir>
Original: new check script.
"""
import os
import sys

import numpy as np

# ---- paths and settings ------------------------------------------------------
FILES = ['lnscale_-1.npy', 'var_-1.npy']

orig_dir, new_dir = sys.argv[1], sys.argv[2]
for f in FILES:
    a = np.load(os.path.join(new_dir, f))
    b = np.load(os.path.join(orig_dir, f))
    print(f'{f:15s} shape {a.shape} dtype {a.dtype}  identical: {np.array_equal(a, b)}'
          f'  max abs diff: {np.max(np.abs(a - b)):.3e}')
    print('   new :', np.array2string(a, precision=17))
    print('   orig:', np.array2string(b, precision=17))
