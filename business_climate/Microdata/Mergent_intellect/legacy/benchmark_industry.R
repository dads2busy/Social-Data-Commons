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



## Business count (Employer firms) --------------------------------------------

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
#mi_employerfirms_industry$MI_percent <- round(100*prop.table(mi_employerfirms_industry$MI_count),2)

mi_nonemployerfirms_industry <- mi_industry %>% 
  filter(sole_proprietor==1) %>%
  select(naics_name,naics_code,MI_count)
#mi_nonemployerfirms_industry$MI_percent <- round(100*prop.table(mi_nonemployerfirms_industry$MI_count),2)


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
    ABS_count=as.numeric(str_replace(number_firms,',',''))) %>%
  filter(!(naics_code=='00')) %>%
  select(naics_code,ABS_count)

# merge the two data
temp <- merge(mi_employerfirms_industry, abs_employerfirms_industry, by.x='naics_code', by.y='naics_code', all.x=T, all.y=T)



# QCWE
qcew_data <- read_csv('Microdata/QCEW/data/working/fairfaxdata.csv')

# treatment
qcew_industry <- qcew_data %>%
  filter(year==2017) %>%
  group_by(naics_name=industry_title) %>%
  summarise(qcew_count=sum(annual_avg_estabs_count, na.rm=T)) %>%
  mutate(naics_code=case_when(
    naics_name=='NAICS 11 Agriculture, forestry, fishing and hunting' ~ '11',
    naics_name=='NAICS 21 Mining, quarrying, and oil and gas extraction' ~ '21',
    naics_name=='NAICS 22 Utilities' ~ '22',
    naics_name=='NAICS 23 Construction' ~ '23',
    naics_name=='NAICS 31-33 Manufacturing' ~ '31-33',
    naics_name=='NAICS 42 Wholesale trade' ~ '42',
    naics_name=='NAICS 44-45 Retail trade' ~ '44-45',
    naics_name=='NAICS 48-49 Transportation and warehousing' ~ '48-49',
    naics_name=='NAICS 51 Information' ~ '51',
    naics_name=='NAICS 52 Finance and insurance' ~ '52',
    naics_name=='NAICS 53 Real estate and rental and leasing' ~ '53',
    naics_name=='NAICS 54 Professional and technical services' ~ '54',
    naics_name=='NAICS 56 Administrative and waste services' ~ '56',
    naics_name=='NAICS 61 Educational services' ~ '61',
    naics_name=='NAICS 62 Health care and social assistance' ~ '62',
    naics_name=='NAICS 71 Arts, entertainment, and recreation' ~ '71',
    naics_name=='NAICS 72 Accommodation and food services' ~ '72',
    naics_name=='NAICS 81 Other services, except public administration' ~ '81',
    naics_name=='NAICS 99 Unclassified' ~ '99',
    naics_name=='NAICS 55 Management of companies and enterprises' ~ '55',
    naics_name=='NAICS 92 Public administration' ~ '92',
    naics_name=='Total for all sectors' ~ '00') ) %>%
  select(naics_code,qcew_count)

#merge with qcew
all_employers <- merge(temp, qcew_industry, by.x='naics_code', by.y='naics_code', all.x=T, all.y=T)

#temp01 <- temp %>% mutate(`ABS_count/MI_count`=ABS_count/MI_count, `ABS_percent/MI_percent`=ABS_percent/MI_percent)
#, ABS_percent = round(100*ABS_count/sum(ABS_count, na.rm=T),2)




# Non employer firms ---------------------------------------------------------------

# NED data
ned_data <- read_csv('Microdata/ABS_census/data/working/NONEMP2017_nonemployer_firms_by_industry_race.csv')
names <- c('geo_name',
           'naics_code',
           'naics_name',
           'legal_form',
           'size',
           'year',
           'number_firms',
           'sales')
colnames(ned_data) <- names

ned_industry <- ned_data %>%
  select(naics_code,ned_count=number_firms) %>%
  filter(!(naics_code=='00')) %>%
  mutate(ned_percent = round(100*ned_count/sum(ned_count, na.rm=T),2))
  
# merge mi with ned 
all_nonemployer <- merge(mi_nonemployerfirms_industry, ned_industry, by.x='naics_code', by.y='naics_code', all.x=T, all.y=T)

#temp_all <- temp %>% mutate(`NED_count/MI_count`=ned_count/MI_count, `NED_percent/MI_percent`=ned_count/MI_percent)



## Employment ---------------------------------------------------------------------------------------------------

# Mergent Intellect
mi_employment_industry <- mi_fairfax_features %>%
  filter(year==2017) %>%
  filter(sole_proprietor==0) %>%
  group_by(naics_name) %>%
  summarise(MI_employment_count = sum(employment, na.rm=T) ) %>%
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
    naics_name=='Public Administration' ~ '92')) %>%
  select(naics_name,naics_code,MI_employment_count) 

#mi_employment_industry$MI_employment_percent <- round(100*prop.table(mi_employment_industry$MI_employment_count),2)

  
# Annual Business Survey
abs_employment_industry <- abs_data %>% 
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
    ABS_employment_count=as.numeric(str_replace(employment,',','')) ) %>%
  filter(!(naics_code=='00')) %>%
  select(naics_code,ABS_employment_count)
#ABS_employment_percent = round(100*ABS_employment_count/sum(ABS_employment_count, na.rm=T),2)

tempa <- merge(mi_employment_industry, abs_employment_industry, by.x='naics_code', by.y='naics_code', all.x=T, all.y=T)


# Lodes data
lodes_data <- read_csv('Microdata/Lodes/data/working/va_lodes_bg_tr_co_20102019.csv.xz')

lodes_employment_industry <- lodes_data %>%
  filter(year==2017) %>%
  group_by(naics_name) %>%
  summarise(lodes_employment_count=sum(jobs, na.rm=T)) %>%
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
    naics_name=='Industries not classified' ~ '99',
    naics_name=='Management of Companies and Enterprises' ~ '55',
    naics_name=='Public Administration' ~ '92',
    naics_name=='Total for all sectors' ~ '00') ) %>%
  select(naics_code,lodes_employment_count)
tempb <- merge(tempa, lodes_employment_industry, by.x='naics_code', by.y='naics_code', all.x=T, all.y=T)


# QCWE
qcew_data <- read_csv('Microdata/QCEW/data/working/fairfaxdata.csv')

# treatment
qcew_employment_industry <- qcew_data %>%
  filter(year==2017) %>%
  group_by(naics_name=industry_title) %>%
  summarise(qcew_employment_count=sum(annual_avg_emplvl, na.rm=T)) %>%
  mutate(naics_code=case_when(
      naics_name=='NAICS 11 Agriculture, forestry, fishing and hunting' ~ '11',
      naics_name=='NAICS 21 Mining, quarrying, and oil and gas extraction' ~ '21',
      naics_name=='NAICS 22 Utilities' ~ '22',
      naics_name=='NAICS 23 Construction' ~ '23',
      naics_name=='NAICS 31-33 Manufacturing' ~ '31-33',
      naics_name=='NAICS 42 Wholesale trade' ~ '42',
      naics_name=='NAICS 44-45 Retail trade' ~ '44-45',
      naics_name=='NAICS 48-49 Transportation and warehousing' ~ '48-49',
      naics_name=='NAICS 51 Information' ~ '51',
      naics_name=='NAICS 52 Finance and insurance' ~ '52',
      naics_name=='NAICS 53 Real estate and rental and leasing' ~ '53',
      naics_name=='NAICS 54 Professional and technical services' ~ '54',
      naics_name=='NAICS 56 Administrative and waste services' ~ '56',
      naics_name=='NAICS 61 Educational services' ~ '61',
      naics_name=='NAICS 62 Health care and social assistance' ~ '62',
      naics_name=='NAICS 71 Arts, entertainment, and recreation' ~ '71',
      naics_name=='NAICS 72 Accommodation and food services' ~ '72',
      naics_name=='NAICS 81 Other services, except public administration' ~ '81',
      naics_name=='NAICS 99 Unclassified' ~ '99',
      naics_name=='NAICS 55 Management of companies and enterprises' ~ '55',
      naics_name=='NAICS 92 Public administration' ~ '92',
      naics_name=='Total for all sectors' ~ '00') ) %>%
    select(naics_code,qcew_employment_count)
all_employment <- merge(tempb, qcew_employment_industry, by.x='naics_code', by.y='naics_code', all.x=T, all.y=T)
  



# merge mi with abs
temp03 <- temp %>% mutate(`ABS_employment_count/MI_employment_count`=ABS_employment_count/MI_employment_count, `ABS_employment_percent/MI_employment_percent`=ABS_employment_percent/MI_employment_percent)










# Minority-owned businesses -----------------------------------------------------

abs_minority <- abs_data %>% 
  filter(naics_name=='Total for all sectors') %>% 
  filter(race %in% c('Minority','Equally minority/nonminority','Nonminority')) %>%
  mutate(class=if_else(race=='Nonminority','Nonminority','Minority'),
         ABS_count=as.numeric(str_replace(number_firms,',','')),
         ABS_employment=as.numeric(str_replace(employment,',',''))) %>%
  group_by(class) %>%
  summarise(ABS_count=sum(ABS_count,na.rm=T),
            ABS_employment=sum(ABS_employment,na.rm=T)) %>%
  select(class,ABS_count,ABS_employment) 

mi_minority <- mi_fairfax_features %>%
  filter(year==2017) %>%
  filter(sole_proprietor==0) %>%
  mutate(class=if_else(minority==0,'Nonminority','Minority')) %>%
  group_by(class) %>%
  summarise(MI_count = length(unique(duns)),
            MI_employment = sum(employment, na.rm=T))

all_minority <- merge(abs_minority, mi_minority, by.x='class', by.y='class', all.x=T, all.y=T)



# Race profile Census
abs_race <- abs_data %>% 
  filter(naics_name=='Total for all sectors') %>% 
  filter(race %in% c('White','Black or African American','American Indian and Alaska Native','Asian','Native Hawaiian and Other Pacific Islander')) %>%
  select(race,number_firms,employment)





# Analyse the Minority registration from SBSD ---------------------------------------------
sbsd_data <- read_csv('Microdata/sbsd_downloaded/data/working/sbsd_minorityregistered_fairfax.csv.xz')

temp <- mi_fairfax_features %>% mutate(company_name01=tolower(company_name)) %>% unique() 
company_list <- unique(temp)

temp01 <- sbsd_data %>%
  mutate(company_name01=tolower(company_name),
         mergent=if_else(company_name01 %in% company_list,1,0)) 







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


