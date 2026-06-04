"""Per-dataset regeneration manifest for the census10to20 remediation.

Each entry: topic dir, ordered entrypoints (module-relative path : function),
and the distribution-file glob(s) the acceptance test reads.

Phase 3b adds the composite entries (their entrypoint sequences vary and are
confirmed when that phase runs). 3a covers the uniform base-ACS group.
"""

INGEST = "code/distribution/ingest.py:run"
PREPARE = "code/distribution/prepare.py:run"
MEASURE_INFO = "data/distribution/measure_info.json"


def _base(topic, glob):
    return {"topic": topic, "entrypoints": [INGEST, PREPARE], "dist_glob": glob,
            "measure_info": MEASURE_INFO}


BASE_ACS = [
    _base("demographics/Age", "data/distribution/*age_demographics.csv.xz"),
    _base("demographics/Race", "data/distribution/*race*.csv.xz"),
    _base("demographics/Gender", "data/distribution/*gender*.csv.xz"),
    _base("demographics/Language", "data/distribution/*language*.csv.xz"),
    _base("demographics/Veteran", "data/distribution/*veteran*.csv.xz"),
    _base("demographics/Population Density", "data/distribution/*population_density*.csv.xz"),
    _base("demographics/Cooperative extension", "data/distribution/*.csv.xz"),
    _base("demographics/Geographic Mobility (HOI)", "data/distribution/*mobility*.csv.xz"),
    _base("financial_well_being/Household Income", "data/distribution/*income*.csv.xz"),
    _base("financial_well_being/Income Inequality", "data/distribution/*inequality*.csv.xz"),
    _base("financial_well_being/Employment Rates", "data/distribution/*employment*.csv.xz"),
    _base("financial_well_being/Material_Deprivation", "data/distribution/*material*.csv.xz"),
    _base("health/System Usage and Insurance/Without Health Insurance", "data/distribution/*insurance*.csv.xz"),
    _base("education/Years of Schooling", "data/distribution/*schooling*.csv.xz"),
    _base("education/Postsecondary", "data/distribution/*postsecondary*.csv.xz"),
    _base("broadband/Household Broadband", "data/distribution/*broadband*.csv.xz"),
    _base("transportation/Population Characteristics", "data/distribution/*population_characteristics*.csv.xz"),
]
