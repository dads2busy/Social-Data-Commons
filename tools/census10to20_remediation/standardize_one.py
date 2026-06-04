"""Regenerate one dataset (ingest via run_entrypoint -> no __main__ auto-publish) and run
the region-wide conservation gate. Usage: python standardize_one.py "<topic dir>"."""
import sys, glob
sys.path.insert(0, "tools/census10to20_remediation")
from driver import run_entrypoint
from acceptance_test import check_conservation
def main(topic):
    run_entrypoint(topic + "/code/distribution/ingest.py", "run")
    fail = False; geo20 = geo10 = False
    import pandas as pd
    for f in sorted(glob.glob(topic + "/data/distribution/*.csv.xz")):
        r = check_conservation(f)
        print(f"  {f.split('/')[-1]}: gate={r['status']} max_ratio={r.get('max_ratio')}")
        if r["status"] == "fail": fail = True
        ms = pd.read_csv(f, usecols=["measure"]).measure
        geo20 = geo20 or ms.str.endswith("_geo20").any()
        geo10 = geo10 or ms.str.endswith("_geo10").any()
    print(f"GEO20={geo20} GEO10={geo10} GATE={'FAIL' if fail else 'PASS'}")
    sys.exit(1 if (fail or not geo20) else 0)
if __name__ == "__main__": main(sys.argv[1])
