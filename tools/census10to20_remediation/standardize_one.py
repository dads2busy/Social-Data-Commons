"""Regenerate one dataset (ingest + prepare via run_entrypoint -> no __main__ auto-publish)
and run the region-wide conservation gate. Usage: python standardize_one.py "<topic dir>".

Runs BOTH entrypoints because prepare re-aggregates (e.g. county -> health district) and
writes its own data/distribution files; those must carry the standardized measures too.
Fails if any distribution file containing tract rows lacks _geo20 (stale/non-standardized).
"""
import sys, glob
sys.path.insert(0, "tools/census10to20_remediation")
from driver import run_entrypoint
from acceptance_test import check_conservation
import pandas as pd

def main(topic):
    run_entrypoint(topic + "/code/distribution/ingest.py", "run")
    run_entrypoint(topic + "/code/distribution/prepare.py", "run")
    fail = False
    any_geo20 = False
    stale = []
    for f in sorted(glob.glob(topic + "/data/distribution/*.csv.xz")):
        r = check_conservation(f)
        d = pd.read_csv(f, usecols=lambda c: c in ("measure", "region_type"))
        if "measure" not in d.columns:
            print(f"  {f.split('/')[-1]}: skipped (no 'measure' column)")
            continue
        ms = d["measure"]
        has_geo20 = ms.str.endswith("_geo20").any()
        has_geo10 = ms.str.endswith("_geo10").any()
        has_tract = ("region_type" in d.columns) and (d["region_type"] == "tract").any()
        print(f"  {f.split('/')[-1]}: gate={r['status']} max_ratio={r.get('max_ratio')} "
              f"geo20={has_geo20} geo10={has_geo10} tract={has_tract}")
        if r["status"] == "fail":
            fail = True
        any_geo20 = any_geo20 or has_geo20
        if has_tract and not has_geo20:
            stale.append(f.split("/")[-1])
    if stale:
        print("STALE (tract data not standardized):", stale)
    print(f"ANY_GEO20={any_geo20} STALE={len(stale)} GATE={'FAIL' if fail else 'PASS'}")
    sys.exit(1 if (fail or not any_geo20 or stale) else 0)

if __name__ == "__main__":
    main(sys.argv[1])
