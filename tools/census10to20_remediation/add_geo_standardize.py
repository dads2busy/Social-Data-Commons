"""Add geo_standardize blocks to a dataset's measure_info.json by name rule.
Usage: python add_geo_standardize.py "<topic dir>"
count := name endswith _count/_cnt OR in {population, Minority_employment, Nonminority_employment}
replicate := everything else. Never overwrites an existing geo_standardize block."""
import json, sys
from pathlib import Path
COUNT_EXACT = {"population", "Minority_employment", "Nonminority_employment"}
def mtype(name): return "count" if (name.endswith(("_count", "_cnt")) or name in COUNT_EXACT) else "replicate"
def main(topic):
    p = Path(topic) / "data/distribution/measure_info.json"
    mi = json.load(open(p)); changed = 0
    for k, v in mi.items():
        if k.startswith("_") or not isinstance(v, dict) or "geo_standardize" in v: continue
        v["geo_standardize"] = {"measure_type": mtype(k)}; changed += 1
    json.dump(mi, open(p, "w"), indent=2, ensure_ascii=False)
    print(f"{topic}: added {changed} geo_standardize blocks")
if __name__ == "__main__": main(sys.argv[1])
