"""Pack the staged record tree (stage_outputs.py) into the files uploaded to Zenodo.

Zenodo records hold a flat list of files, so each top-level folder becomes one zip:
    README.md, md5sums.txt              documentation/ (plain files, so Zenodo shows them)
    input_data.zip                      input_data/
    DA_experiments_<yy>_<G*E>.zip       DA_experiments/<yy>_<G*E>/ (one zip per experiment)
    website_data.zip                    website_data/
The zips keep the paths of the tree: unzipping all of them in one folder gives back the tree, with
README.md and md5sums.txt next to it (md5sum -c md5sums.txt then checks every file). Already
compressed files (.gz, the website packs .bin) are stored, the others deflated. Every zip is read back:
member list and sizes equal to the tree, CRCs checked.

Inputs:  /global/scratch/users/marcomaz/zenodo_outputs (the record tree)
Outputs: /global/scratch/users/marcomaz/zenodo_upload (the files of the Zenodo record)
Environment: any Python 3
Run: in sbatch_stage_outputs.sh, after stage_outputs.py
"""
import os
import shutil
import zipfile

SCRATCH = "/global/scratch/users/marcomaz"
TREE = os.path.join(SCRATCH, "zenodo_outputs")
UPLOAD = os.path.join(SCRATCH, "zenodo_upload")
STORED = (".gz", ".bin")


def tree_files(top):
    """Files under TREE/top, as paths relative to TREE."""
    return sorted(os.path.relpath(os.path.join(r, f), TREE) for r, _, fs in os.walk(os.path.join(TREE, top)) for f in fs)


def pack(name, top):
    dst = os.path.join(UPLOAD, name)
    files = tree_files(top)
    with zipfile.ZipFile(dst, "w", allowZip64=True) as z:
        for f in files:
            z.write(os.path.join(TREE, f), f,
                    compress_type=zipfile.ZIP_STORED if f.endswith(STORED) else zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(dst) as z:
        assert z.testzip() is None, f"{name}: CRC error"
        got = {i.filename: i.file_size for i in z.infolist()}
    assert got == {f: os.path.getsize(os.path.join(TREE, f)) for f in files}, f"{name}: members differ from the tree"
    raw = sum(got.values())
    print(f"{name}: {len(files)} files, {raw / 1e6:.0f} -> {os.path.getsize(dst) / 1e6:.0f} MB, CRCs ok", flush=True)


def main():
    os.makedirs(UPLOAD, exist_ok=True)
    for f in os.listdir(UPLOAD):
        os.remove(os.path.join(UPLOAD, f))
    for f in ("README.md", "md5sums.txt"):
        shutil.copy2(os.path.join(TREE, "documentation", f), os.path.join(UPLOAD, f))
    pack("input_data.zip", "input_data")
    for exp in sorted(os.listdir(os.path.join(TREE, "DA_experiments"))):
        pack(f"DA_experiments_{exp}.zip", os.path.join("DA_experiments", exp))
    pack("website_data.zip", "website_data")
    n = sum(len(tree_files(t)) for t in ("input_data", "DA_experiments", "website_data"))
    listed = sum(1 for _ in open(os.path.join(TREE, "documentation", "md5sums.txt")))
    assert n == listed, f"{n} files in the zips, {listed} in md5sums.txt"
    tot = sum(os.path.getsize(os.path.join(UPLOAD, f)) for f in os.listdir(UPLOAD))
    print(f"done: {len(os.listdir(UPLOAD))} files, {tot / 1e9:.2f} GB in {UPLOAD}", flush=True)


if __name__ == "__main__":
    main()
