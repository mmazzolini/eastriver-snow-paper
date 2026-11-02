"""Compare scaler files written by s1_fit_scaler.py with the original scaler.save.

Loads each scaler with joblib and compares the feature order (feature_names_in_),
mean_, scale_, var_ and n_samples_seen_ with the original: exact equality and
maximum absolute difference.

Inputs:  original scaler file; one or more new scaler files.
Outputs: text on stdout.
Environment: conda env gpy-env (scikit-learn 1.8.0, needed to load the original pickle).
Run:     python checks/check_s1_scaler.py <original scaler.save> <new1> [<new2> ...]
Original: new check script.
"""
import sys
import warnings

import joblib
import numpy as np

# ---- paths and settings ------------------------------------------------------
FIELDS = ['mean_', 'scale_', 'var_']

orig_path, new_paths = sys.argv[1], sys.argv[2:]
with warnings.catch_warnings():
    warnings.simplefilter('ignore')  # version warnings when loading pickles of other sklearn versions
    orig = joblib.load(orig_path)
    print('original', orig_path)
    print('  feature order:', list(orig.feature_names_in_))
    print('  n_samples_seen_:', orig.n_samples_seen_)
    for p in new_paths:
        new = joblib.load(p)
        print('new', p)
        same_names = list(new.feature_names_in_) == list(orig.feature_names_in_)
        print('  feature order identical:', same_names)
        print('  n_samples_seen_ identical:', np.array_equal(new.n_samples_seen_, orig.n_samples_seen_))
        for f in FIELDS:
            a, b = getattr(new, f), getattr(orig, f)
            print(f'  {f:7s} identical: {np.array_equal(a, b)}   max abs diff: {np.max(np.abs(a - b)):.3e}'
                  f'   max rel diff: {np.max(np.abs(a - b) / np.abs(b)):.3e}')
