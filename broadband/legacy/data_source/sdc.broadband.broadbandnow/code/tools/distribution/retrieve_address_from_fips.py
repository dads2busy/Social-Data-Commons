import pandas as pd
import geopandas as gpd
import random
import numpy as np
from geopy.point import Point
from shapely.geometry import Point as sPoint
import matplotlib.pyplot as plt
from geopy.geocoders import Nominatim
from tqdm import tqdm
import pathlib
import sys
import math
import time
import os
from pathlib import Path

"""
Iterate across each county, use reverse geocoding on 10 random location per census block and get an address
Then, remove duplicates and save back to the original data frame. Worry about verifying the freshness of the address later
"""

START_TIME = time.time()


def get_lat_longs(gdf, geoid, geo_column_id, points_per_geo=10):
    aoi = gdf[gdf[geo_column_id].str[: len(geoid)] == geoid]
    aoi_geom = aoi.unary_union

    # find area bounds
    bounds = aoi_geom.bounds
    xmin, ymin, xmax, ymax = bounds

    xext = xmax - xmin
    yext = ymax - ymin

    points = []
    while len(points) < points_per_geo:
        # generate a random x and y
        x = xmin + random.random() * xext
        y = ymin + random.random() * yext
        p = sPoint(x, y)
        if aoi_geom.contains(p):  # check if point is inside geometry
            points.append(p)

    return points


geolocator = Nominatim(user_agent="test")


def reverse_geocoding(lat, lon):
    try:
        location = geolocator.reverse(Point(lat, lon))
        return location.raw["display_name"]
    except KeyboardInterrupt:
        sys.exit()
    except:
        return None


def get_address_df(geoid, geo_column_id="GEOID20", num_tries=1, progress_bar=False):
    # shape_file_url = os.path.join(
    #     str(Path.home()),
    #     "Documents/GitHub/national_address_database/data/shapefiles/tl_2020_{county}_tabblock20.zip",
    # )
    shape_file_url = "https://www2.census.gov/geo/tiger/TIGER2020PL/LAYER/TABBLOCK/2020/tl_2020_{county}_tabblock20.zip"

    county = geoid[:5]
    # Download the shapefiles
    gdf = gpd.read_file(shape_file_url.format(county=county))
    dfs = []

    gdf["layer"] = gdf[geo_column_id].str[
        : len(geoid)
    ]  # variable based on the resolution

    # Filter based on the variable resolution
    gdf = gdf[gdf["layer"] == geoid]
    empty_bar = gdf["layer"].unique()
    if progress_bar:
        empty_bar = tqdm(gdf["layer"].unique())

    for geoid in empty_bar:
        if progress_bar:
            empty_bar.set_description("Extracting lat long for: %s" % geoid)
        pdf = pd.DataFrame()
        pts = get_lat_longs(gdf, geoid, geo_column_id, points_per_geo=num_tries)
        pdf["geometry"] = pts
        pdf["longitude"] = pdf["geometry"].apply(lambda x: x.x)
        pdf["latitude"] = pdf["geometry"].apply(lambda x: x.y)
        pdf[geo_column_id] = geoid
        # print(pdf)
        dfs.append(pdf)
    rgeo_df = pd.concat(dfs)

    # rgeo_df = rgeo_df.head(11)  # for quicker testing
    # Set a batch size limit of 2000
    batch_size = 500
    addresses = []
    batch_bar = list(range(int(math.ceil(len(rgeo_df) / batch_size))))
    if progress_bar:
        batch_bar = tqdm(range(int(math.ceil(len(rgeo_df) / batch_size))))

    for i in batch_bar:
        if progress_bar:
            batch_bar.set_description(
                "Processing batch (%s/%s), size: %s"
                % (
                    i + 1,
                    int(math.ceil(len(rgeo_df) / batch_size)),
                    len(rgeo_df["latitude"][i * batch_size : (i + 1) * batch_size]),
                )
            )

        addresses.extend(
            np.vectorize(reverse_geocoding)(
                rgeo_df["latitude"][i * batch_size : (i + 1) * batch_size],
                rgeo_df["longitude"][i * batch_size : (i + 1) * batch_size],
            )
        )

        if progress_bar:
            batch_bar.set_description("Changing ip address")

    rgeo_df["address"] = addresses
    rgeo_df = rgeo_df.drop_duplicates(subset=["address"])
    assert len(rgeo_df["address"].unique()) <= num_tries
    return rgeo_df


if __name__ == "__main__":
    """
    Given a list of geoids, return a data frame with the addresses and coordinates. Since duplicates can be returned, changed names to num_tries instead
    """
    adf = get_address_df(
        "010070100011", geo_column_id="GEOID20", num_tries=20, progress_bar=True
    )
    print(adf)
    """Example Output
                                         geometry  longitude   latitude       GEOID20                                            address
0   POINT (-87.25736286376787 33.124283835619245) -87.257363  33.124284  010070100011                Bibb County, Alabama, United States
2    POINT (-87.25601947319642 33.09498856500362) -87.256019  33.094989  010070100011  Cedar Crest Road, Bibb County, Alabama, United...
3    POINT (-87.22836567767575 33.12168156482637) -87.228366  33.121682  010070100011  Vance Road, Johnstown, Vance, Bibb County, Ala...
5   POINT (-87.16355795048375 33.140662977897726) -87.163558  33.140663  010070100011  1204, Frog Level Road, Shawtown, Bibb County, ...
6    POINT (-87.24088120461876 33.09453353614123) -87.240881  33.094534  010070100011  North Scottsville Road, Bibb County, Alabama, ...
16   POINT (-87.26024515399548 33.08785251970028) -87.260245  33.087853  010070100011  Serty Boyd Road, Stewart Settlement, Bibb Coun...
18   POINT (-87.22202043517181 33.09789725040032) -87.222020  33.097897  010070100011  142, Twinview Way, Bibb County, Alabama, 35184...
19  POINT (-87.24757122031166 33.077011143426965) -87.247571  33.077011  010070100011  Tin Top Lane, Stewart Settlement, Bibb County,...    
    """
