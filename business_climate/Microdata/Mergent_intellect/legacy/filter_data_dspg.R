# this file filter the data for the dspg project

# libraries ---------------------------------------------------------------------
library(readr)
library(dplyr)
library(stringr)
library(tigris)
library(sf)
library(data.table)
library(ggplot2)
library(reshape2)
library(crosstable)
library(tidyr)
library(scales)
library(tidygeocoder)
library(fuzzyjoin)
library(zipcodeR)


# load mergent intellect ------------------------------------
details <- read_csv("Microdata/Mergent_intellect/data/working/mi_companies_details.csv.xz")
operations <- read_csv("Microdata/Mergent_intellect/data/working/mi_financial_info.csv.xz")
executives <- read_csv("Microdata/Mergent_intellect/data/working/mi_executives.csv.xz")


# data treatment -----------------------------------------------------------------
fairfax_details <- details %>%
  filter(`Physical County`=='FAIRFAX') %>% 
  select(duns = `D-U-N-S@ Number`,
         company_name=`Company Name`,
         founding_year = `Year of Founding`,
         minority = `Minority Owned Indicator`,
         primary_naics = `Primary NAICS Code`,
         address= `Physical Address`, 
         county= `Physical County`, 
         city=`Physical City`, 
         zipcode=`Physical Zipcode`, 
         state = `Physical State`,
         primary_naics = `Primary NAICS Code`,
         latitude=Latitude, 
         longitude=Longtitude) %>%
  mutate(minority=if_else(minority=='No',0,1))

fairfax_operation <- operations %>%
  select(company_name=`Company Name`,
         duns = `D-U-N-S@ Number`,
         measure,
         value,
         year) %>%
  filter(measure %in% c('Employee This Site')) %>%
  filter(duns %in% unique(fairfax_details$duns)) %>%
  filter(year %in% c("2010","2011","2012","2013","2014","2015","2016","2017","2018","2019","2020")) %>%
  mutate(year=as.numeric(year),
         employment=as.numeric(gsub('[$,]','',value)),
         flag_soleproprietor=if_else(employment==0,1,0),
         flag_small=if_else(employment<=50,1,0)) %>%
  select(company_name,duns,year, employment,flag_soleproprietor,flag_small)

fairfax_executives <- executives %>%
  select(duns = `D-U-N-S@ Number`,
         company_name=`Company Name`,
         firstname= `First Name`,
         lastname = `Last Name`,
         title = `Title`,
         gender= `Gender`) %>%
  filter(duns %in% unique(fairfax_details$duns))


# save the data -----------------------------------------------------------------
readr::write_csv(fairfax_details, xzfile('/home/yhu2bk/Github/dspg23businessclimate/data/mergent_and_library/mi_address_details.csv.xz', compression = 9))
readr::write_csv(fairfax_operation, xzfile('/home/yhu2bk/Github/dspg23businessclimate/data/mergent_and_library/mi_operation.csv.xz', compression = 9))
readr::write_csv(fairfax_executives, xzfile('/home/yhu2bk/Github/dspg23businessclimate/data/mergent_intellect_executives/mi_executives.csv.xz', compression = 9))



