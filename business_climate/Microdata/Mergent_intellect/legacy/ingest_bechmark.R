# Build data for bechnmarking

# library --------------------------------------------------------------------------
library(dplyr)
library(sf)
library(httr)
library(sp)
library(data.table)
library(stringr)
library(tidyr)
library(readr)
library(tidyverse)
library(tidycensus)
library(tigris)
library(rjson)
library(jsonlite)
library(dplyr)




# Mergent Intellect data ------------------------------------------------

# Load data
uploadpath = "Microdata/Mergent_intellect/data/working/"
mi_fairfax_features <-  read_csv(paste0(uploadpath,"mi_fairfax_features_updated.csv.xz"))

# Data treatment
mi_industry <- mi_fairfax_features %>%
  filter(year==2017) %>%
  group_by(naics_name,sole_proprietor) %>%
  summarise(MI_count = length(unique(duns))) %>%
  mutate(naics_code=case_when(
    naics_name=='Agriculture, Forestry, Fishing and Hunting' ~ '11',
    naics_name=='Mining, Quarrying, and Oil and Gas Extraction' ~ '21',
    naics_name=='Utilities' ~ '22',
    naics_name=='Construction' ~ '23',
    naics_name=='Manufacturing' ~ '31-33',
    naics_name=='Wholesale Trade' ~ '42',
    naics_name=='Retail Trade' ~ '44-45',
    naics_name=='Transportation and Warehousing' ~ '48-49',
    naics_name=='Information' ~ '51',
    naics_name=='Finance and Insurance' ~ '52',
    naics_name=='Real Estate and Rental and Leasing' ~ '53',
    naics_name=='Professional, Scientific, and Technical Services' ~ '54',
    naics_name=='Administrative and Support and Waste Management and Remediation Services' ~ '56',
    naics_name=='Educational Services' ~ '61',
    naics_name=='Health Care and Social Assistance' ~ '62',
    naics_name=='Arts, Entertainment, and Recreation' ~ '71',
    naics_name=='Accommodation and Food Services' ~ '72',
    naics_name=='Other Services (except Public Administration)' ~ '81',
    naics_name=='Nonclassifiable Establishments' ~ '99',
    naics_name=='Management of Companies and Enterprises' ~ '55',
    naics_name=='Public Administration' ~ '92'))
  
mi_employerfirms_industry <- mi_industry %>% 
  filter(sole_proprietor==0) %>%
  select(naics_name,naics_code,MI_count)
mi_employerfirms_industry$MI_percent <- round(100*prop.table(mi_employerfirms_industry$MI_count),2)

mi_nonemployerfirms_industry <- mi_industry %>% 
  filter(sole_proprietor==1) %>%
  select(naics_name,naics_code,MI_count)
mi_nonemployerfirms_industry$MI_percent <- round(100*prop.table(mi_nonemployerfirms_industry$MI_count),2)





# Annual Business Survey -------------------------------------------------

# Load the data
abs_data <- read_csv('Microdata/ABS_census/data/working/ABSCS2017_employer_firms_by_industry_race.csv')
names <- c('geo_name',
           'naics_code',
           'naics_name',
           'sex',
           'ethnicity',
           'race',
           'veteran',
           'year',
           'number_firms',
           'sales',
           'employment',
           'payroll',
           'moe_number_firms',
           'moe_sales',
           'moe_employment',
           'moe_payroll')
colnames(abs_data) <- names


# Data treatment
abs_employerfirms_industry <- abs_data %>% 
  filter(race=='Total') %>% 
  mutate(naics_code=case_when(
    naics_name=='Agriculture, forestry, fishing and hunting (660)' ~ '11',
    naics_name=='Mining, quarrying, and oil and gas extraction' ~ '21',
    naics_name=='Utilities' ~ '22',
    naics_name=='Construction' ~ '23',
    naics_name=='Manufacturing' ~ '31-33',
    naics_name=='Wholesale trade' ~ '42',
    naics_name=='Retail trade' ~ '44-45',
    naics_name=='Transportation and warehousing (661)' ~ '48-49',
    naics_name=='Information' ~ '51',
    naics_name=='Finance and insurance (662)' ~ '52',
    naics_name=='Real estate and rental and leasing' ~ '53',
    naics_name=='Professional, scientific, and technical services' ~ '54',
    naics_name=='Administrative and support and waste management and remediation services' ~ '56',
    naics_name=='Educational services' ~ '61',
    naics_name=='Health care and social assistance' ~ '62',
    naics_name=='Arts, entertainment, and recreation' ~ '71',
    naics_name=='Accommodation and food services' ~ '72',
    naics_name=='Other services (except public administration) (663)' ~ '81',
    naics_name=='Industries not classified' ~ '99',
    naics_name=='Management of companies and enterprises' ~ '55',
    naics_name=='Total for all sectors' ~ '00'),
    ABS_count=as.numeric(str_replace(number_firms,',','')),
    ABS_percent = round(100*ABS_count/sum(ABS_count, na.rm=T),2)) %>%
  filter(!(naics_code=='00')) %>%
  select(naics_code,ABS_count,ABS_percent)


# merge mi with abs 
temp <- merge(mi_employerfirms_industry, abs_employerfirms_industry, by.x='naics_code', by.y='naics_code', all.x=T, all.y=T)
temp <- temp %>% mutate(`ABS_count/MI_count`=ABS_count/MI_count, `ABS_percent/MI_percent`=ABS_percent/MI_percent)



















abs_race <- abs_data %>% 
  filter(naics_name=='Total for all sectors') %>% 
  select(geo_name,race,year,number_firms,employment,moe_number_firms,moe_employment) %>%
  filter(race %in% c('White','Black or African American','American Indian and Alaska Native','Asian','Native Hawaiian and Other Pacific Islander'))

abs_minority <- abs_data %>% 
  filter(naics_name=='Total for all sectors') %>% 
  select(geo_name,race,year,number_firms,employment,moe_number_firms,moe_employment) %>%
  filter(race %in% c('Minority','Equally minority/nonminority','Nonminority'))

















# identify minority companies that have been registered using sbsd
mi_fairfax_features01 <- mi_fairfax_features %>%
  mutate(company_name01=tolower(company_name),
         registered=if_else(company_name01 %in% company_list,1,0)) 

temp <- mi_fairfax_features01 %>% filter(minority==1)
mesgent_mi_list <- unique(temp$company_name01)




# filter company by minority
temp_minority <- mi_fairfax_features %>%
  filter(year==2017) %>%
  group_by(minority,sole_proprietor) %>%
  summarise(numb_companies = length(unique(duns)),
            total_employment=sum(employment))

temp_employer_minority <- temp_minority %>% filter(sole_proprietor==0)
temp_nonemployer_minority <- temp_minority %>% filter(sole_proprietor==1)


