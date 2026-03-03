# select and compute the key variables for analysis

# library
library(readr)
library(dplyr)
library(stringr)
library(tigris)
library(sf)
library(data.table)
library(ggplot2)
library(reshape2)
library(tidyr)


# load the companies details data -------------------------------------------------------------- 
path = "Microdata/Mergent_intellect/data/working/"
companies <-  read_csv(paste0(path,"mi_ncr_companies_details.csv.xz")) %>%
  select(company_name=`Company Name`,
         duns = `D-U-N-S@ Number`,
         company_type = `Company Type`,
         founding_year = `Year of Founding`,
         minority = `Minority Owned Indicator`,
         primary_naics = `Primary NAICS Code` ) 

# data treatment
temp <- companies %>%
  mutate(minority = if_else(minority=='Yes',1,0),
         naics2=as.numeric(substr(primary_naics, 1, 2)),
         naics_name=case_when(
           naics2==11 ~ "Agriculture, Forestry, Fishing and Hunting",
           naics2==21 ~ "Mining, Quarrying, and Oil and Gas Extraction",
           naics2==22 ~ "Utilities",
           naics2==23 ~ "Construction",
           naics2==31 | naics2==32 | naics2==33 ~ "Manufacturing",
           naics2==42 ~ "Wholesale Trade",
           naics2==44 | naics2==45 ~ "Retail Trade",
           naics2==48 | naics2==49 ~ "Transportation and Warehousing",
           naics2==51 ~ "Information",
           naics2==52 ~ "Finance and Insurance",
           naics2==53 ~ "Real Estate and Rental and Leasing",
           naics2==54 ~ "Professional, Scientific, and Technical Services",
           naics2==55 ~ "Management of Companies and Enterprises",
           naics2==56 ~ "Administrative and Support and Waste Management and Remediation Services",
           naics2==61 ~ "Educational Services",
           naics2==62 ~ "Health Care and Social Assistance",
           naics2==71 ~ "Arts, Entertainment, and Recreation",
           naics2==72 ~ "Accommodation and Food Services",
           naics2==81 ~ "Other Services (except Public Administration)",
           naics2==92 ~ "Public Administration",
           naics2==99 ~ "Nonclassifiable Establishments"))


# load financial infos and tract small companies  --------------------------------------------------
operation <-  read_csv(paste0(path,"mi_ncr_financial_info.csv.xz")) %>%
  select(company_name=`Company Name`,
         duns = `D-U-N-S@ Number`,
         measure,
         value,
         year) %>%
  filter(measure %in% c( 'Sales Volume', 'Employee This Site' , 'Calculated Tax Rate %')) %>%
  filter(year %in% c("2010","2011","2012","2013","2014","2015","2016","2017","2018","2019","2020")) %>%
  mutate(year=as.numeric(year),
         value=as.numeric(gsub('[$,]','',value))) %>%
  pivot_wider(names_from = measure, values_from = value) %>%
  select(company_name,
         duns,
         year,
         sales= `Sales Volume`,
         employment = `Employee This Site`)

# data treatment: company size
temp1 <- operation %>%
  mutate(small = if_else(employment<50,1,0),
         sole_proprietor =if_else(employment==1,1,0))

# tract entry an exit
min_year <- min(temp1$year)
max_year <- max(temp1$year)
duns_after_time <- unique(temp1$duns[temp1$year>min_year])
temp2 <- temp1 %>% filter(year==min_year) %>% mutate(entry=NA, exit=if_else(duns %in% duns_after_time,0,1))

for (time in min(temp1$year)+1:max(temp1$year)){
  duns_prior_time <- unique(temp1$duns[temp1$year<time])
  duns_after_time <- unique(temp1$duns[temp1$year>time])
  temp3 <- temp1 %>% filter(year==time) %>% mutate(entry=if_else(duns %in% duns_prior_time,0,1), exit=if_else(duns %in% duns_after_time,0,1))
  temp2 <- rbind(temp2,temp3)
}
temp2 <- temp2 %>% mutate(exit=if_else(year==max_year,0,exit))


# geolocate all the companies and combine with all the infos ----------------------------------
ncr_bg2010 <-  read_csv(paste0(path,"mi_ncr_geolocated_bg2010.csv.xz")) 
ncr_bg2020 <-  read_csv(paste0(path,"mi_ncr_geolocated_bg2020.csv.xz")) 


# merge all the data and save ------------------------------------------------
feature <- merge(temp, temp2, by.x=c('duns','company_name'), by.y=c('duns','company_name')) 
feature_bg2010 <- merge(feature[feature$year<2020,], ncr_bg2010, by.x=c('duns','company_name'), by.y=c('duns','company_name')) 
feature_bg2020 <- merge(feature[feature$year>2019,], ncr_bg2020, by.x=c('duns','company_name'), by.y=c('duns','company_name')) 
feature_bg <- rbind(feature_bg2010,feature_bg2020)

# save the data
readr::write_csv(feature_bg, xzfile(paste0(path,"mi_ncr_features_bg.csv.xz"), compression = 9))

