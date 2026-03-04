import pandas as pd

#%%
# QHP Marketplace insurance premium data, scraped from Kaiser Family Foundation calculator
qhp_market = pd.read_csv('~/git/cost-living/Health care cost/data/Working/kff_marketplace_premium.csv')
qhp_market.fips = qhp_market.fips.astype('int').astype('str').str.zfill(5)
qhp_market.Zip_Code = qhp_market.Zip_Code.astype('int').astype('str').str.zfill(5)

# Average employee contribution to health insurance, from MEPS-IC data tool
meps_ic_raw = pd.read_csv('~/git/cost-living/Health care cost/data/Original/meps_premium_by_state_2021.csv')
meps_ic = meps_ic_raw[meps_ic_raw['Measure Names'] == 'Estimate']
state_avg = meps_ic.pivot(index='State', columns='Type', values='Measure Values')

# make index out of each county's marketplace cost of silver plan, unsubsidized
# with the state average as each state's benchmark
qhp_market['price_index'] = qhp_market.groupby('State')[
    'Raw_Cost_of_Silver'].apply(lambda x: x/x.mean())

# use the index to calculate each county's average cost for each coverage
county_premium = pd.merge(qhp_market.loc[:,[
    'State', 'County', 'Zip_Code', 'fips', 'price_index']], state_avg, on='State')
county_premium = county_premium.apply(
    lambda x: x * county_premium.price_index / 12 if (
    (str(x.dtype)=='float64') & (x.name != 'price_index')
    ) else x, axis=0)
county_premium.drop('price_index', inplace=True, axis=1)

#%%
# This is the survey consolidated data for MEPS-HC 2019 survey. I saved only 3 variables of interest
meps_hc_raw = pd.read_csv('~/git/cost-living/Health care cost/data/Original/meps_hc_consolidated_2019.csv')

region_dict = {
    1: ('Connecticut', 'Maine', 'Massachusetts', 'New Hampshire', 'New Jersey',
        'New York', 'Pennsylvania', 'Rhode Island', 'Vermont'),
    2: ('Indiana', 'Illinois', 'Iowa', 'Kansas', 'Michigan', 'Minnesota',
        'Missouri', 'Nebraska', 'North Dakota', 'Ohio', 'South Dakota', 'Wisconsin'),
    3: ('Alabama', 'Arkansas', 'Delaware', 'District of Columbia', 'Florida',
        'Georgia', 'Kentucky', 'Louisiana', 'Maryland', 'Mississippi', 'North Carolina',
        'Oklahoma', 'South Carolina', 'Tennessee', 'Texas', 'Virginia', 'West Virginia'),
    4: ('Alaska', 'Arizona', 'California', 'Colorado', 'Hawaii', 'Idaho', 'Montana',
        'Nevada', 'New Mexico', 'Oregon', 'Utah', 'Washington', 'Wyoming')
    }

meps_hc = meps_hc_raw.rename({'TOTSLF19': 'expense', # total paid by self and family
                              'REGION19': 'region', # census region of residence
                              'AGE19X': 'age' # age as of Dec 31, 2019
                              }, axis=1)
# clear unapplicable entries
meps_hc = meps_hc[(meps_hc.region != -1) & (meps_hc.age != -1)]
# convert age into category
meps_hc['age'] = pd.cut(meps_hc['age'], bins=[0, 2, 5, 12, 17, 200],
                        labels=['infant', 'preschooler', 'school-age',
                                'teenager', 'adult'])
# take group average by region and age, divided by 12 to get monthly
expense_avg = meps_hc.groupby(['region', 'age'])['expense'].mean()/12
expense_avg = expense_avg.unstack(level=1)

# expand the regional expense data to county
expense_avg.rename(index=region_dict, inplace=True)
expense_avg = expense_avg.reset_index().explode('region').reset_index(drop=True)
expense_avg.rename(columns={'region': 'State'}, inplace=True)
#%%
# join two datasets together
combined = pd.merge(county_premium, expense_avg, on='State')

# adjust for inflation according to Labor Statistic's API 2020 and 2021 on
# annual avg price level of Medical Service, retrived from http://www.bls.gov/cpi/
prices = pd.read_csv('data/original/medical_inflation.csv', header=0, index_col=(0))['Annual']
inflation = prices[2021] / prices[2019]
combined = combined.apply(lambda x: x * inflation if str(x.dtype)=='float64' else x, axis=0)

#%%
combined.to_csv('~/git/cost-living/Health care cost/data/Working/us_ct_meps_kff_2019_2021_healthcarecost.csv')
