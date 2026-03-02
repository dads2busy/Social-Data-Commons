# compare HOI from Rex with SDAD value

library(readr)
library(readxl)
library(dplyr)

# load data
sdad <- read_csv('Geographic Mobility (HOI)/data/distribution/va_cttrbg_acs_2015_2021_moving_demographics.csv.xz') %>%
  select(geoid,year,mobility_sdad=value)
rex <- read_excel('Geographic Mobility (HOI)/data/working/HOI V3_14 Variables_Raw Scores.xlsx') %>%
  select(geoid=CT2,mobility_rex=`Mobility*`)

# comparison for a given year
tyear <- 2020
temp <- sdad %>% filter(year==tyear)
temp1 <- merge(rex, temp, by='geoid')

# comparison
plot(temp1$mobility_rex,temp1$mobility_sdad, xlab='geographic mobility (Rex)', ylab='geographic mobility (SDAD)')
title(main='Census data for 2020')
