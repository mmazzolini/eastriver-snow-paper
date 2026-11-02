// Check docs/js/core.js against the notebook reference written by build_web_data.py.
//
// For every run, at the default settings of its year: the profile steps, the cells and IC2 cells used,
// every profile value, the field point, the IC2 point, the profile scores, the KDE values, profile 2 on
// its IC2 track, the gridded products along the profiles and one segment per profile must agree with
// the full-precision Python values (members are stored to the cm, so tolerance 6 mm; IC2 members
// and ASO are stored to the mm; elevation is stored as float32, tolerance 1 cm). It also checks the merged range requests and the fallback for a
// server that ignores Range.
//
// Run (compute node): node web/check_core.mjs [data dir]     (conda env "webcheck", Node 20)
import { readFile, open } from "node:fs/promises";
import * as core from "../docs/js/core.js";

const BASE = process.argv[2] || "/global/scratch/users/marcomaz/web_data/";
let requests = 0;

function localFetcher(ignoreRange = false) {
  const whole = new Map();
  return {
    async get(name) { requests++; return new Uint8Array(await readFile(BASE + name)); },
    async range(name, start, len) {
      requests++;
      if (ignoreRange) {                       // like a server that answers 200 with the whole file
        if (!whole.has(name)) whole.set(name, new Uint8Array(await readFile(BASE + name)));
        return whole.get(name).subarray(start, start + len);
      }
      const fh = await open(BASE + name);
      const b = Buffer.alloc(len);
      await fh.read(b, 0, len, start);
      await fh.close();
      return new Uint8Array(b.buffer, b.byteOffset, len);
    },
  };
}

let failures = 0;
function check(label, got, want, tol) {
  const g = Array.from(got ?? [], Number), w = Array.from(want ?? [], (v) => (v === null ? NaN : Number(v)));
  if (g.length !== w.length) { failures++; console.log(`  FAIL ${label}: length ${g.length} vs ${w.length}`); return; }
  let worst = 0, bad = 0;
  for (let i = 0; i < g.length; i++) {
    if (Number.isNaN(g[i]) && Number.isNaN(w[i])) continue;
    const d = Math.abs(g[i] - w[i]);
    if (!(d <= tol)) bad++;
    if (Number.isFinite(d)) worst = Math.max(worst, d); else worst = Infinity;
  }
  if (bad) failures++;
  console.log(`  ${bad ? "FAIL" : "ok  "} ${label}: n ${g.length}, max |diff| ${worst.toExponential(2)}${bad ? `, ${bad} beyond ${tol}` : ""}`);
}

const MM = 1.0e-3, CM = 6.0e-3;
for (const ignoreRange of [false, true]) {
  console.log(`\n===== range requests ${ignoreRange ? "ignored by the server (whole files)" : "served"}`);
  const S = await new core.Store(localFetcher(ignoreRange)).init();
  for (const [id, meta] of Object.entries(S.m.runs)) {
    if (ignoreRange && id !== "24GP") continue;
    const ref = JSON.parse(await readFile(`${BASE}reference_${id}.json`, "utf8"));
    const Y = await S.year(String(meta.year));
    const R = await S.run(id);
    const d = Y.defaults;
    console.log(`--- ${id} (${meta.run})`);
    // profile 2 lies on its IC2 track: the track line must give the default (notebook) line
    const trk = Y.tracks[d.p2.track], TL = core.trackLine(trk, d.p2.y0, d.p2.y1);
    check("profile 2 on its track (x0, x1)", [TL.x0, TL.x1], [d.p2.x0, d.p2.x1], 1e-6);
    console.log(`  tracks: ${Y.tracks.map((t) => `${t.label} ${t.n} cells${t.paper ? " [paper]" : ""}`).join("; ")}`);
    const P1 = core.stripSteps(S, d.p1), P2 = core.lineSteps(S, { ...d.p2, ...TL });
    requests = 0;
    await S.ensureTiles([id], [...core.stepCells(P1), ...core.stepCells(P2)]);
    console.log(`  tiles loaded with ${requests} requests`);
    check("profile 1 rows", Array.from({ length: d.p1.nrows }, (_, i) => d.p1.row0 + i), ref.rows_L, 0);
    check("profile 1 Easting (m)", P1.coord.map((v) => v * 1000), ref.xl, 0.06);
    check("profile 2 Northing (m)", P2.coord.map((v) => v * 1000), ref.yl, 0.06);
    for (const [P, key] of [[P1, "PL"], [P2, "PR"]]) {
      const V = core.computeProfile(S, Y, [id], P, { q: d.q, minCells: d.min_cells });
      const r = V.runs[id], w = ref[key];
      check(`${key}.z`, V.z, w.z, 0.01);
      check(`${key}.aso`, V.aso, w.aso, MM);
      for (const k of ["mean", "prior", "lo", "hi", "plo", "phi"]) check(`${key}.${k}`, r[k], w[k], CM);
      check(`${key}.memb`, r.memb, w.memb.flat(), CM);
      check(`${key}.pmemb`, r.pmemb, w.pmemb.flat(), CM);
      const sc = r.score, ws = ref.scores[key === "PL" ? "L" : "R"];
      check(`${key} scores`, [sc.n, sc.biasPost, sc.rmsePost, sc.crpsPost, sc.biasPrior, sc.rmsePrior, sc.crpsPrior],
        [ws.n, ws.biasPost, ws.rmsePost, ws.crpsPost, ws.biasPrior, ws.rmsePrior, ws.crpsPrior], CM);
      for (const [pid, pr] of Object.entries(Y.prods)) {
        const PV = core.productProfile(S, Y, pr.v, P, { minCells: d.min_cells });
        check(`${key} ${pr.label}`, PV.vals, w[`prod_${pid}`], MM);
      }
    }
    check("IC2 cells in profile 1", core.ic2InStrip(S, R.ic2, d.p1), ref.sel_L, 0);
    const selR = core.ic2NearLine(R.ic2, { ...d.p2, ...TL }, d.p2.cap);
    check("IC2 cells in profile 2", selR, ref.sel_R, 0);
    check("IC2 cells of profile 2 on its track", selR.map((i) => Y.ic2_track[i]), selR.map(() => d.p2.track), 0);
    const iIc2 = selR.reduce((b, i) => (Math.abs(R.ic2.y[i] - d.ic2.n) < Math.abs(R.ic2.y[b] - d.ic2.n) ? i : b), selR[0]);
    check("IC2 point", [iIc2], [ref.ic2.i], 0);
    check("IC2 point members", R.ic2.post[iIc2], ref.ic2.post, MM);
    const col = core.fieldColumn(S, Y, d.p1, d.field.e, d.field.snap);
    const rows = Array.from({ length: d.p1.nrows }, (_, i) => d.p1.row0 + i);
    const F = core.fieldPoint(S, Y, [id], rows, col);
    check("field column", [col], [ref.field.col], 0);
    check("field point post", F.runs[id].post, ref.field.post, CM);
    check("field point prior", F.runs[id].prior, ref.field.prior, CM);
    check("field point ASO, z", [F.aso, F.z], [ref.field.aso, ref.field.z], 0.01);
    const g = Float64Array.from(ref.kde.grid);
    check("KDE field point", core.kde(F.runs[id].post, g), ref.kde.field_post, 1e-2);
    check("KDE IC2 point", core.kde(R.ic2.post[iIc2], g), ref.kde.ic2_post, 2e-3);
    const srt = Float64Array.from(R.ic2.post[iIc2]).sort();
    check("CRPS IC2 point", [core.crpsSorted(srt, R.ic2.aso[iIc2])], [ref.crps_ic2], MM);
    // segment of profile 1: columns with centres in [e0, e1] (as the page), per-member means over the cells
    const sL = ref.seg.L;
    const c0 = Math.ceil((sL.e0 - S.gx[0]) / S.dx), c1 = Math.floor((sL.e1 - S.gx[0]) / S.dx);
    check("segment 1 columns", [c0, c1], [sL.c0, sL.c1], 0);
    const FS = core.fieldSegment(S, Y, [id], rows, c0, c1);
    check("segment 1 cells", [FS.cells.length], [sL.n], 0);
    check("segment 1 post", FS.runs[id].post, sL.post, CM);
    check("segment 1 prior", FS.runs[id].prior, sL.prior, CM);
    check("segment 1 ASO, z", [FS.aso, FS.z], [sL.aso, sL.z], 0.01);
    for (const [pid, pr] of Object.entries(Y.prods)) check(`segment 1 ${pr.label}`, [core.meanOver(pr.v, FS.cells)], [sL.prods[pid]], MM);
    // segment of profile 2: the IC2 cells of the profile with Northing in [n0, n1]
    const sR = ref.seg.R;
    const idx = selR.filter((i) => R.ic2.y[i] >= sR.n0 && R.ic2.y[i] <= sR.n1);
    check("segment 2 IC2 cells", idx, sR.idx, 0);
    const G = core.ic2Segment(R.ic2, idx);
    check("segment 2 post", G.post, sR.post, 1e-6);   // reference written to 1e-6 m
    check("segment 2 prior", G.prior, sR.prior, 1e-6);   // reference written to 1e-6 m
    check("segment 2 obs, r, ASO", [G.obs, G.r, G.aso], [sR.obs, sR.r_mean, sR.aso], 1e-4);
  }
}
console.log(failures ? `\n${failures} CHECKS FAILED` : "\nALL CHECKS PASSED");
process.exit(failures ? 1 : 0);
