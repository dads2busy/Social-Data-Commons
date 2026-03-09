import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Import the tract conversion functions
from utils.distribution.Example.example import standardize_all

# Reading 5 years (2017-2021) Townsend Index (Material Deprivation Index) by tract, county, and health district
data = pd.read_csv(
    "utils/distribution/Example/va_hdcttr_vdh_2017_2021_material_deprivation_index.csv.xz"
)

# Filter to years and region_type that need to be redistributed
data = data[data["year"] <= 2019]
data = data[data["region_type"] == "tract"]

# Use the standardize function
standardized_data = standardize_all(data)

# This function produces both standardized and original values (see the measure variable)

# Producing two maps with standardized and original index values for the year 2019
standardized_data = standardized_data[standardized_data["year"] == 2019]
standardized_data_std = standardized_data[standardized_data["measure"] == "material_deprivation_indicator_std"]
standardized_data_org = standardized_data[standardized_data["measure"] == "material_deprivation_indicator_orig_2010"]

# Getting tract shape files for VA
# Using geopandas to read census tract shapefiles
# Note: In Python, we'd typically download these files from the Census Bureau website
# or use the cenpy package instead of tigris
virginia_tracts_2010 = gpd.read_file(
    "https://www2.census.gov/geo/tiger/TIGER2010/TRACT/2010/tl_2010_51_tract10.zip"
)
virginia_tracts_2020 = gpd.read_file(
    "https://www2.census.gov/geo/tiger/TIGER2020/TRACT/tl_2020_51_tract.zip"
)

# Extract GEOID
virginia_tracts_2010["geoid"] = virginia_tracts_2010["GEOID10"]
virginia_tracts_2020["geoid"] = virginia_tracts_2020["GEOID"]

# Convert standardized_data to geopandas dataframes
standardized_data_std = pd.DataFrame(standardized_data_std)
standardized_data_org = pd.DataFrame(standardized_data_org)

# Merging the standardized and original files with shapefiles
standardized_data_std = virginia_tracts_2020.merge(
    standardized_data_std,
    on="geoid",
    how="left"
)

standardized_data_org = virginia_tracts_2010.merge(
    standardized_data_org,
    on="geoid",
    how="inner"
)

# Ensure output directory exists
Path("utils/distribution/Example").mkdir(parents=True, exist_ok=True)

# Making maps for comparison - Standardized data (2020 boundaries)
fig, ax = plt.subplots(figsize=(10, 8))
median_value = standardized_data_std["value"].median()

standardized_data_std.plot(
    ax=ax,
    column="value",
    cmap="Reds",
    missing_kwds={
        "color": "lightgrey"
    },
    vmin=0,
    vmax=0.5,
    legend=True,
    legend_kwds={
        "label": "Value",
        "orientation": "horizontal"
    }
)

ax.set_title('Townsend Index - Standardized')
ax.set_axis_off()
plt.tight_layout()
plt.savefig("utils/distribution/Example/standardized.png", dpi=300)
plt.close()

# Making maps for comparison - Original data (2010 boundaries)
fig, ax = plt.subplots(figsize=(10, 8))
median_value = standardized_data_org["value"].median()

standardized_data_org.plot(
    ax=ax,
    column="value",
    cmap="Reds",
    missing_kwds={
        "color": "lightgrey"
    },
    vmin=0,
    vmax=0.5,
    legend=True,
    legend_kwds={
        "label": "Value",
        "orientation": "horizontal"
    }
)

ax.set_title('Townsend Index - Original')
ax.set_axis_off()
plt.tight_layout()
plt.savefig("utils/distribution/Example/original.png", dpi=300)