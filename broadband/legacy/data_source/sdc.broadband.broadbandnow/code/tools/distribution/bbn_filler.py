# imports
# generic imports
import numpy as np
import re
import os
import time
import pandas as pd
import random
from bs4 import BeautifulSoup
from tqdm import tqdm
from slugify import slugify
import math
import argparse
from pprint import pprint
import traceback
import logging
import pathlib
import json
import ast
import sys
import traceback
import requests
from datetime import datetime
import warnings

from retrieve_address_from_fips import get_address_df
from bbn import set_up_driver, query_bbn


def save_concat_to_path(new_df, old_df_path, old_df_geoid="GEOID20"):
    # Check if the file exist. If it does, read and save to path. Otherwise, just save to path. Only works if the column names are the same
    merged = None
    if os.path.isfile(old_df_path):
        df = pd.read_csv(old_df_path, dtype={old_df_geoid: object})
        # print("-" * 80)
        # print(set(df.columns).symmetric_difference(set(new_df.columns)))
        # print(set(df.columns))
        # print(set(new_df.columns))
        # print(set(df.columns) - set(new_df.columns))
        # print("-" * 80)
        merged = pd.concat([new_df, df])
    else:
        merged = new_df
    merged.to_csv(old_df_path, index=False)
    return merged


if __name__ == "__main__":
    output_dir = "../../data/"
    warnings.filterwarnings("ignore")

    with open("../../data/missing_census_block_grps.txt", "r") as f:
        s = eval(f.read())
    missing_bg = sorted(s)

    # For each missing geoid, check whether the issue has been resolved
    pbar = tqdm(missing_bg)
    for geoid in pbar:
        pbar.set_description("Parsing: %s" % geoid)
        county = geoid[:5]
        small_output_dir = output_dir + "_%s.csv.xz/" % county
        os.system("mkdir -p %s" % output_dir)

        # Since the save file is at a county level, we might be saving to the county file multiple times
        output_file_name = os.path.join(output_dir, "%s.csv.xz" % county)

        """
        The conditions that need to be met when starting a bbn query, is if:
            1) The file does not exist
            2) The file exists, but the geoid does not exist in the file
        The conditions tht need to be met to skip, is:
            1) if the file exists and the geoid exists        
        """

        geoid_exists = os.path.isfile(output_file_name) and any(
            pd.read_csv(output_file_name, dtype={"GEOID20": object})["GEOID20"].str[
                : len(geoid)
            ]
            == geoid
        )

        if geoid_exists:
            pbar.set_description("Geoid already exists for: %s" % output_file_name)
            # Skip if the geoid already exists
            continue

        price_df = None
        num_tries = 1
        while price_df is None:
            pbar.set_description("Searching, tries: %s" % (num_tries))
            adf = get_address_df(geoid, geo_column_id="GEOID20", num_tries=num_tries)
            if adf.empty:
                num_tries *= 2
                continue

            dfs = []
            apbar = tqdm(adf["address"].unique())
            driver, wait = set_up_driver(headless=True)
            for address in apbar:
                apbar.set_description("Parsing: %s" % address)
                df = query_bbn(driver, wait, address)
                if df is None:  # if nothing is returned, skip
                    continue
                df["GEOID20"] = geoid
                df["latitude"] = adf[adf["address"] == address]["latitude"].values[0]
                df["longitude"] = adf[adf["address"] == address]["longitude"].values[0]
                if not df is None and not df.empty:
                    dfs.append(df)
            driver.quit()

            if len(dfs) > 0:
                price_df = pd.concat(dfs)
            num_tries *= (
                2  # Increase the number of samples by a factor of 2 every time it fails
            )

        save_concat_to_path(price_df, output_file_name)
        pbar.set_description(
            "Updating %s with %s addresses"
            % (output_file_name, len(price_df["address"].unique()))
        )
