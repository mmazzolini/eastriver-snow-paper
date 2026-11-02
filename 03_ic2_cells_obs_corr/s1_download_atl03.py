"""Download of ICESat-2 ATL03 photons over the East River basin with SlideRule (YAPC photon scores).

The bounding box of the East River basin outline is sent to SlideRule with a list of
ATL03 granules; SlideRule subsets them into 20 m photon segments and returns every
photon (all confidences) with its ATL08 photon class and YAPC photon density score.
The photon positions are projected to UTM 13N (EPSG:32613) and written as a feather
file indexed by photon time.

The file used later (ATL03_yapc.feather) holds the two release-006 granules of
2023-03-31 (rgt 150) and 2023-04-01 (rgt 173) with all ATL08 photon classes (0-4);
the defaults below are those granules and classes. The last saved settings of the
original notebook differ: CMR listing of 2022-11-01 to 2023-06-01 (8 granules), ATL08
class "atl08_ground" only, output ATL03_winter_yapc.feather. In October 2026 NASA CMR
no longer lists release-006 granules (--cmr then returns an empty list; release 007
is listed), while SlideRule still processes the 006 granules by name. YAPC "version"
is set to 3 explicitly: with the SlideRule default of client/server 5.6.3 the scores
differ from the file used, with version 3 they are identical (see README, Checks).

Inputs:  East River outline (shapefile); internet access to SlideRule (and NASA CMR for --cmr).
Outputs: feather file (one row per photon; columns as returned by SlideRule
         plus x, y in EPSG:32613; index: time).
Environment: Python with the SlideRule client (pip install sliderule geopandas pyarrow).
         The original "sliderule_env" (Jupyter kernel "sliderule_k", Python 3.12) no
         longer exists; the check used sliderule client 5.6.3 (server v5.6.3).
Run:     sbatch sbatch_s1_download_atl03.sh <out.feather> [--granules G1.h5 ...]
         (python s1_download_atl03.py --out <file> [--granules ...] [--cmr --t0 ... --t1 ...])
Original: /global/home/users/marcomaz/B/ICESat-2/B_IS2_download.ipynb cells 1-2, 4, 6, 9, 12, 14, 18-19
          (run outside Savio); file used: /global/home/groups/fc_mgirotto/East_River_Data/IS2/ATL03_yapc.feather.
"""
import argparse

import geopandas as gpd
import pyarrow.feather as feather
from sliderule import earthdata, icesat2

# ---- paths and settings ------------------------------------------------------
SHAPEFILE = "/global/home/groups/fc_mgirotto/East_River_Data/shp/eastriver.shp"
SLIDERULE_URL = "slideruleearth.io"          # public SlideRule service (sliderule.service_url in the original)
RELEASE = "006"                              # ATL03 release
TIME_START, TIME_END = "2023-03-31", "2023-04-02"         # used only with --cmr
GRANULES = ["ATL03_20230331045749_01501906_006_02.h5",      # granules of the file used
            "ATL03_20230401164153_01731902_006_02.h5"]      # (as listed by CMR in the original notebook)
ATL08_CLASSES = ["atl08_noise", "atl08_ground", "atl08_canopy", "atl08_top_of_canopy", "atl08_unclassified"]
YAPC = dict(version=3, knn=0, win_h=3, win_x=5, min_ph=0, score=0)   # version 3 reproduces the scores of the file used
OUT_CRS = "EPSG:32613"                       # UTM 13N
# -------------------------------------------------------------------------------


def coords2poly(coords):
    """Bounding box [xmin, ymin, xmax, ymax] -> closed SlideRule polygon."""
    poly = [{'lon': coords[0], 'lat': coords[1]},
            {'lon': coords[2], 'lat': coords[1]},
            {'lon': coords[2], 'lat': coords[3]},
            {'lon': coords[0], 'lat': coords[3]},
            {'lon': coords[0], 'lat': coords[1]}]
    return poly


p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
p.add_argument("--out", required=True, help="output feather file")
p.add_argument("--t0", default=TIME_START)
p.add_argument("--t1", default=TIME_END)
p.add_argument("--atl08-classes", nargs="+", default=ATL08_CLASSES)
p.add_argument("--granules", nargs="+", default=GRANULES, help="ATL03 granule names")
p.add_argument("--cmr", action="store_true", help="list the granules of t0..t1 in NASA CMR instead of --granules")
a = p.parse_args()

east_river = gpd.read_file(SHAPEFILE)
coords = east_river.geometry.total_bounds
print("bounding box (lon/lat)", coords, flush=True)
region = coords2poly(coords)

icesat2.init(url=SLIDERULE_URL, verbose=True)

parms = {
    # extent and time
    "poly": region,
    "t0": a.t0,
    "t1": a.t1,
    # processing parameters
    "srt": icesat2.SRT_LAND,
    "len": 20,
    "pass_invalid": True,          # also return segments that fail the checks
    "cnf": -2,                     # all photons
    "atl08_class": a.atl08_classes,
    "yapc": YAPC,
}

if a.cmr:
    granules_list = earthdata.cmr(short_name='ATL03', polygon=region, time_start=a.t0,
                                  time_end=a.t1, version=RELEASE)
else:
    granules_list = a.granules
print("granules", granules_list, flush=True)

atl03 = icesat2.atl03sp(parms, resources=granules_list)

# projected coordinates as columns, no geometry
atl03 = atl03.to_crs(OUT_CRS)
atl03['x'] = atl03.geometry.x
atl03['y'] = atl03.geometry.y
atl03 = atl03.drop(columns={'geometry'})

with open(a.out, 'wb') as f:
    feather.write_feather(atl03, f)
print(f"wrote {a.out}: {len(atl03)} photons", flush=True)
