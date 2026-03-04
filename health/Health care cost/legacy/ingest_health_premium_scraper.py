import pandas as pd
import regex as re
import time

from selenium.webdriver import Chrome
from selenium.webdriver import ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
import selenium.common.exceptions

from tqdm import tqdm

import plotly.figure_factory as ff
import matplotlib.pyplot as plt
#%%
ops = ChromeOptions()
# ops.add_argument('--headless')
ops.add_argument('--ignore-certificate-errors')
ops.add_argument('--ignore-ssl-errors')
ops.add_argument('--window-size=1200,720')  # to ensure no content is hidden if in smaller windows
ops.add_argument('--log-level=3')
ops.add_experimental_option('excludeSwitches', ['enable-logging'])
driver = Chrome(options=ops, service=Service(
    executable_path='chromedriver_win32/chromedriver.exe'))

driver.get('https://www.kff.org/interactive/subsidy-calculator-2021/')

try:  # click the "accept cookies collection" button, if presented
    wait = WebDriverWait(driver, 10)
    wait.until(EC.element_to_be_clickable((By.ID, 'hs-eu-confirmation-button')))
    driver.find_element(By.ID, 'hs-eu-confirmation-button').click()
except selenium.common.exceptions.NoSuchElementException:
    pass

#%%
isPctPoverty = False
income = 120000

isSpouseCovered = False

number_of_adults = 1
number_of_children = 0

adult_age = 30
child_age = 14
#%%
# Instantiate the search, span necessary elements in the page
# This cell until next #%% doesn't matter
state_input = driver.find_element(By.ID, 'state-dd')
state_input.send_keys('Virginia')

zip_input = driver.find_element(By.NAME, 'zip')
zip_input.clear()
zip_input.send_keys(22901)

try:
    skip_select = False
    local_input = driver.find_element(By.NAME, 'locale')
#    wait = WebDriverWait(driver, 1)
#    wait.until(EC.element_to_be_clickable((By.NAME, 'locale')))
#except selenium.common.exceptions.TimeoutException:
except selenium.common.exceptions.NoSuchElementException:
    skip_select = True
    pass
if not skip_select:
    try:
        local_input.click()
        local_input.send_keys('Charlotttesville')
    except selenium.common.exceptions.StaleElementReferenceException:
        # this "stale element" is a weired bug. Solved by re-defining the element
        local_input = driver.find_element(By.NAME, 'locale')
        local_input.click()
        local_input.send_keys('Charlotttesville')
    
# threshold for income, used to determine tax subsidies
income_botton = driver.find_element(By.ID, 'dollars')
pct_poverty_botton = driver.find_element(By.ID, 'percent')

if isPctPoverty:
    pct_poverty_botton.click()

income_input = driver.find_element(By.NAME, 'income')
income_input.clear()
income_input.send_keys(income)

# whether spouse's employer provides coverage
spouse_job_cover_botton_yes = driver.find_element(By.ID, 'employer-coverage-1')
spouse_job_cover_botton_no = driver.find_element(By.ID, 'employer-coverage-0')

if isSpouseCovered:
    spouse_job_cover_botton_yes.click()
else:
    spouse_job_cover_botton_no.click()

# family composition
family_size_input = Select(driver.find_element(By.NAME, 'people'))
family_size_input.select_by_visible_text(str(number_of_adults + number_of_children))

adult_count_input = Select(driver.find_element(By.NAME, 'adult-count'))
adult_count_input.select_by_value(str(number_of_adults))
for i in range(number_of_adults):
    element_name ='adults[{}][age]'.format(i)
    adult_age_input = driver.find_element(By.NAME, element_name)
    adult_age_input.send_keys(adult_age)

child_count_input = Select(driver.find_element(By.NAME, 'child-count'))
child_count_input.select_by_value(str(number_of_children))
for i in range(number_of_children):
    element_name ='children[{}][age]'.format(i)
    child_age_input = driver.find_element(By.NAME, element_name)
    child_age_input.send_keys(child_age)

submit_botton = driver.find_element(
    By.CSS_SELECTOR,'#subsidy-form > p > input[type=submit]:nth-child(2)')
submit_botton.click()

#%%
geo_data = pd.read_csv('~/git/cost-living/Health care cost/data/Original/uszips.csv')
# ignore oversea territories like puerto rico, virgin islands, hawaii, etc.
geo_data = geo_data[~geo_data.state_id.isin(['PR','VI','HI','AS','GU','MP'])]
code_list = geo_data.groupby(['state_name', 'county_name']).head(1)
code_list['zip'] = code_list.zip.astype(str).str.zfill(5)
code_list['fips'] = code_list.county_fips.astype(str).str.zfill(5)
results = pd.DataFrame(
    columns=('State', 'County', 'Zip_Code', 'Subsidized_Cost_of_Silver',
             'Subsidized_Cost_of_Bronze', 'Raw_Cost_of_Silver',
             'Raw_Cost_of_Bronze'))
code_list = code_list.iloc[934:,:]
with tqdm(total = code_list.shape[0], leave=True, position=0,
               bar_format='{desc:<5.5}{percentage:3.0f}%|{bar:60}{r_bar}') as bar:
    for _, (state, county, zip_code, fips) in code_list.loc[:,[
            'state_name','county_name','zip', 'county_fips']].iterrows():
#    for _, (state, county, zip_code) in code_list.loc[:,['State','County','Zip_Code']].iterrows():
        ind = results.shape[0]
        results.loc[ind, 'State'] = state
        results.loc[ind, 'Zip_Code'] = str(zip_code)
        results.loc[ind, 'County'] = county
        results.loc[ind, 'fips'] = str(fips)
        
        state_input.send_keys(state)
        zip_input.send_keys(zip_code)
        
        try:
            local_input = driver.find_element(By.NAME, 'locale')
        except selenium.common.exceptions.NoSuchElementException:
            skip_select = True
            pass
        if not skip_select:
            try:
                local_input.click()
                local_input.send_keys(county)
            except selenium.common.exceptions.StaleElementReferenceException:
                # this "stale element" is a weired bug. Solved by re-defining the element
                local_input = driver.find_element(By.NAME, 'locale')
                local_input.click()
                local_input.send_keys(county)
        
    #    driver.implicitly_wait(1)
    #    wait = WebDriverWait(driver, 10)
    #    wait.until(EC.element_to_be_clickable(submit_botton))
    #    submit_botton.click()
        
        try:
            wait = WebDriverWait(driver, 3)
            wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "h4 ~ p:not(h4)")))
        except selenium.common.exceptions.TimeoutException:
            print('cannot retrieve data for {0} county, {1} {2}'.format(
                county, state, zip_code))
            bar.update(1)
            continue
        
        number_elements = driver.find_elements(By.CLASS_NAME, 'bold-blue')
        try:
            results.loc[ind, 'Subsidized_Cost_of_Silver'] = int(
                number_elements[2].text.strip('$').replace(',',''))
            results.loc[ind, 'Raw_Cost_of_Silver'] = int(
                number_elements[4].text.strip('$').replace(',',''))
        except selenium.common.exceptions.StaleElementReferenceException:
            print('Stale element error when accessing {0} county, {1} {2}'.format(
                county, state, zip_code))
            bar.update(1)
            continue
        
        reg_cost = re.compile(r"\$[0-9,]+")
        text_elements = driver.find_elements(By.CSS_SELECTOR, "h4 ~ p:not(h4)")
        text =  ''
        for i in range(1,3):
            text += text_elements[i].text
        bronze_cost_subsidized, bronze_subsidy = re.findall(reg_cost, text)[0:3:2]
        results.loc[ind, 'Subsidized_Cost_of_Bronze'] = int(
            bronze_cost_subsidized.strip('$').replace(',',''))
        bronze_subsidy = int(bronze_subsidy.strip('$').replace(',',''))
        results.loc[ind, 'Raw_Cost_of_Bronze'] = (
            results.loc[ind, 'Subsidized_Cost_of_Bronze']*12 + bronze_subsidy)//12
        bar.update(1)
#%%
driver.close()

#%%
"""
# make some handy map plots
import plotly.figure_factory as ff
import plotly.io as pio
pio.renderers.default='browser'

import shapely
import warnings
from shapely.errors import ShapelyDeprecationWarning
warnings.filterwarnings("ignore", category=ShapelyDeprecationWarning)


ncr_states = ['Virginia', 'Maryland', 'District of Columbia']

#df = pd.read_csv('2022_07_12-insurance_premium-ver01.csv', index_col=(0))
df = pd.read_csv('kff_marketplace_premium.csv', index_col=(0))
df.fips = df.fips.astype('int').astype(str).str.zfill(5)

ncr_data = df[df.State.isin(ncr_states)]

fig = ff.create_choropleth(
    fips=ncr_data.fips.tolist(), values=ncr_data.Subsidized_Cost_of_Bronze.tolist(),
    county_outline={'color': 'rgb(255,255,255)', 'width': 0.5},
    legend_title='Population per county',
    scope = ncr_states
)

fig.show() 

fig = ff.create_choropleth(
    fips = df.fips.tolist(), values = df.Raw_Cost_of_Silver.tolist(),
    color_continuous_scale="Viridis",
    county_outline={'color': 'rgb(255,255,255)', 'width': 0.5},
    legend_title='Cost of QHP Silver Plan (unsubsidized)'    
    )
fig.show()
"""
#%%
# make some handy map plots
#import plotly.figure_factory as ff
import plotly.io as pio
pio.renderers.default='browser'

import shapely
import warnings
from shapely.errors import ShapelyDeprecationWarning
warnings.filterwarnings("ignore", category=ShapelyDeprecationWarning)

from urllib.request import urlopen
import json
with urlopen('https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json') as response:
    counties = json.load(response)

import plotly.express as px

df = pd.read_csv('data/Working/kff_marketplace_premium.csv', index_col=(0))
df.fips = df.fips.astype('int').astype(str).str.zfill(5)

fig = px.choropleth(df, geojson=counties, locations='fips', color='Raw_Cost_of_Silver',
                    color_continuous_scale = 'Viridis',
                    scope='usa', 
                    labels={'sil': 'Cost of QHP Silver Plan (unsubsidized)'}
                    )
fig.show()
#%%
# manually fill in the missed counties/cities in VA
df = pd.read_csv('data/Working/kff_marketplace_premium.csv', index_col=(0))
df.fips = df.fips.astype('int').astype(str).str.zfill(5)

va_data = df[df['State']=='Virginia']

# this file is downloaded from here
# https://github.com/jalbertbowden/open-virginia-data-toolkit/blame/master/fips/fips-codes-virginia.csv
va_fips = pd.read_csv('va_fips.csv', header=0)

va_fips_cleaned = va_fips[(va_fips['Entity Description'] == 'County') | 
                          (va_fips['Entity Description'] == 'city')]

l1 = []
for i in va_data.County:
    if i not in va_fips_cleaned['GU Name'].tolist():
        l1.append(i)

l2 = []
for i in va_fips_cleaned['GU Name']:
    if i not in va_data['County'].tolist():
        l2.append(i)
print('Counties to be collected manually: ')
counties_tbd = va_fips_cleaned[va_fips_cleaned['GU Name'].isin(l2)]
print(counties_tbd)
# the rest are done manually in excel.
