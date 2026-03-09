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
import traceback
import requests
from datetime import datetime
import warnings

from retrieve_address_from_fips import get_address_df

# selenium imports
import selenium
from selenium import webdriver
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import ElementClickInterceptedException
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.proxy import Proxy, ProxyType
from selenium.webdriver.chrome.service import Service


# check if xpath exists, if not return false
def check_exists_by_xpath(driver, xpath):
    """
    Description:
        Check existence of xpath on page

    Inputs:
        webdriver: your webdriver
        xpath: whatever element we are looking for

    Outputs:
        returns True if xpath exists, False if not
    """
    # try to find element
    try:
        # driver.find_element_by_xpath(xpath)
        driver.find_element("xpath", xpath)

    # throw exception and return false if unable to find
    except NoSuchElementException:
        return False
    return True


def search_address(address, driver, driver_wait=20):
    """
    Description:
        Check existence of xpath on page

    Inputs:
        address: string, single home address we are scraping for
        driver: your webdriver
        driver_wait: integer, wait time for driver - default = 20

    Outputs:
        returns True if xpath exists, False if not
    """
    # wait until search bar is clickable and enter address
    wait = WebDriverWait(driver, driver_wait)
    search = wait.until(EC.element_to_be_clickable((By.ID, "plan-search")))
    search.clear()
    search.send_keys("{}".format(address))

    # sleep, then go to top suggested address
    time.sleep(2)
    go_top = check_exists_by_xpath(
        driver, '//*[@id="plans-search"]/div/div/div[1]/div/div/div/ul'
    )

    # click top address
    if go_top:
        go_top_address = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, '//*[@id="plans-search"]/div/div/div[1]/div/div/div/ul/li')
            )
        )
        go_top_address.click()

    return go_top


def extract_page(address, driver):
    # bs - scrape page
    html = driver.page_source
    soup = BeautifulSoup(html, features="html.parser")

    errors = soup.find_all(attrs={"class": "c-plans-search-error__heading"})

    plan_dfs = []
    # Iterate through each service plan:
    for plan in soup.find_all(attrs={"class": "l-providers-list__item"}):
        # Create empty data frame
        plan_df = pd.DataFrame()
        speed = [
            s.getText()
            for s in plan.find_all(attrs={"class": "c-provider-card__speeds-value"})
        ]
        down_up = [
            s.getText()
            for s in plan.find_all(attrs={"class": "c-provider-card__speeds-label"})
        ]
        price = (
            plan.find(attrs={"class": "c-provider-card__plan-value"})
            .getText()
            .split("$")[-1]
        )
        name = (
            plan.find(attrs={"class": "c-provider-card__provider-name"})
            .getText()
            .split(". ")[1]
        )
        internet_type = (
            plan.find(attrs={"class": "c-provider-card__label"}).getText().strip()
        )

        plan_df["speed"] = speed
        plan_df["down_up"] = down_up
        plan_df["price"] = price
        plan_df["name"] = name
        plan_df["type"] = internet_type
        plan_df["address"] = address
        plan_df["year_parsed"] = datetime.now().strftime("%Y")
        # plan_df["success"] = True

        if plan_df is not None and not plan_df.empty:
            plan_dfs.append(plan_df)

    if len(plan_dfs) > 0:
        df = pd.concat(plan_dfs)
        return df


def scrape_prices(
    driver,
    wait,
    address,
    min_wait=10,
    max_wait=30,
):
    """
    Description:
        Scrape internet packages from Broadbandnow.com - takes each address and scrapes all packages for top match

    Inputs:
        driver: your webdriver
        addresses: array of strings, home addresses we are scraping for (first output of read_and_clean_addresses_for_bgs)

    Outputs:
        df: a data frame containing the columns:
            address: corresponding address of the package
            price: price of the package
            name: name of the package
            type: type of package?
            speed: speed of the package

    """
    if address is None:
        return

    try:
        # reload page to clear results (noticed that we run into issues if we do not clear)
        driver.get("https://broadbandnow.com/compare/plans")
        go_top = search_address(address, driver)

        # select top address
        if not go_top:
            # print('Skipping: Cannot go to the top address')
            return  # skip to next address
        time.sleep(1)
        unable_to_confirm = check_exists_by_xpath(
            driver,
            "/html/body/div[2]/div/div/div[1]/section/section/div/div/div[1]/div/section",
        )

        # if able to confirm and go to top axrddress
        if unable_to_confirm:
            return

        time.sleep(1)
        load_more = check_exists_by_xpath(
            driver, '//*[@id="cityPlansListing"]/section/div/div[2]/div/div/section'
        )

        # if load more is an option, then load all packages
        if load_more:
            # load all plans
            load_all_plans = wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        '//*[@id="cityPlansListing"]/section/div/div[2]/div/div/section',
                    )
                )
            )
            load_all_plans.click()

        adf = extract_page(address, driver)

        # Be respectful of pinging the server
        # time.sleep(random.randint(min_wait, max_wait))

        # select edit option to change address
        edit = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, '//*[@id="plans-search"]/div/div/div/h1/span')
            )
        )
        edit.click()

    # if try fails, throw exception and increment counter (retry until problem_counter hits 5)
    # throws error if we try to edit search plans but this is not an option because nothing was searched after hitting home page
    except TimeoutException as ex:
        # DO something
        # empty.add(address)
        pass
    finally:  # Run regadless
        # with open(empty_file_name, "w") as f:
        #     f.write(str(empty))
        pass
    return adf


def set_up_driver(headless=True):
    # Start Driver
    options = webdriver.ChromeOptions()

    if headless:
        options.add_argument("--headless")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )
    driver.set_page_load_timeout(60 * 1)
    # driver.maximize_window()

    # set driver params
    driver_wait = 5
    wait = WebDriverWait(driver, driver_wait)
    return driver, wait


# Given an address, return a data frame
def query_bbn(driver, wait, address, headless=True):
    price_df = None
    try:
        price_df = scrape_prices(driver, wait, address, 3, 5)
    except Exception as e:
        traceback.print_exc()
        print(e)
    return price_df


if __name__ == "__main__":
    """
    Example: Retrieve n addresses from the shape geometry, and then query those address from broadbandnow and return the results
    """

    adf = get_address_df("01073", geo_column_id="GEOID20", num_tries=5)
    assert not adf.empty
    print(adf)
    driver, wait = set_up_driver(headless=True)

    dfs = []
    apbar = tqdm(adf["address"].unique())
    for address in apbar:
        apbar.set_description("Parsing: %s" % address)
        df = query_bbn(driver, wait, address)
        if df is None:
            continue
        dfs.append(df)

    driver.quit()  # Exit out of the driver
    if len(dfs) > 0:
        final_df = pd.concat(dfs)
        assert not final_df.empty
        print(final_df)
    else:
        print("Final data frame list is empty")

    """
    Example output:
        speed   down_up   price                       name                                          type                                            address year_parsed
0   5000 Mbps  Download     180                 AT&T Fiber                                 Internet 5000  686, Flint Hill Road, Bessemer, Jefferson Coun...        2023
1   5000 Mbps    Upload     180                 AT&T Fiber                                 Internet 5000  686, Flint Hill Road, Bessemer, Jefferson Coun...        2023
0   1200 Mbps  Download      80                    Xfinity                                 Gigabit Extra  686, Flint Hill Road, Bessemer, Jefferson Coun...        2023
1     35 Mbps    Upload      80                    Xfinity                                 Gigabit Extra  686, Flint Hill Road, Bessemer, Jefferson Coun...        2023
0    940 Mbps  Download      70  CenturyLink Fiber Gigabit                                                686, Flint Hill Road, Bessemer, Jefferson Coun...        2023
..        ...       ...     ...                        ...                                           ...                                                ...         ...
1    880 Mbps    Upload  164.99               Verizon Fios  Fios Gigabit Connection + Fios TV Test Drive  I 59, Longmeadow, Cotton Ridge, Trussville, Je...        2023
0    200 Mbps  Download      30  CenturyLink Fiber Gigabit                                                I 59, Longmeadow, Cotton Ridge, Trussville, Je...        2023
1    200 Mbps    Upload      30  CenturyLink Fiber Gigabit                                                I 59, Longmeadow, Cotton Ridge, Trussville, Je...        2023
0    182 Mbps  Download      50  T-Mobile 5G Home Internet                      Home Internet w/ Autopay  I 59, Longmeadow, Cotton Ridge, Trussville, Je...        2023
1     23 Mbps    Upload      50  T-Mobile 5G Home Internet                      Home Internet w/ Autopay  I 59, Longmeadow, Cotton Ridge, Trussville, Je...        2023    
    """
