library(ipumsr)
library(tidyverse)
library(survival)
library(ggfortify)
library(dplyr)
library(readxl)
library(readr)
library(reshape2)



county_fips <- 51059  #Fairfax County, VA 
county_name <- "Fairfax County"

counties_shared_puma <- c(51059, 51610, 51600) #PUMAS include Fairfax County, Fairfax city and Falls Church

name_files <- "fairfax"


library(tidyr)
library(dplyr)


hh <- c('A', 'T', 'S', 'I')

# household 2

hh_2 <- crossing('A', hh) %>% mutate(compos = paste0('A', hh))

length(unique(hh_2$`"A"`))

# household 3
hh_3 <- crossing('A', hh, hh2=hh) %>% mutate(compos = paste0('A', hh, hh2 ))
length(unique(hh_3$compos))


hh_3_final <- vapply(strsplit(hh_3$compos, NULL), function(x) paste(sort(x), collapse = ''), '')
length(unique(hh_3_final))
#
#
# household 4
hh_4 <- crossing('A', hh, hh2=hh, hh3=hh) %>% mutate(compos = paste0('A', hh, hh2, hh3 ))
length(unique(hh_4$compos))


hh_4_final <- vapply(strsplit(hh_4$compos, NULL), function(x) paste(sort(x), collapse = ''), '')
length(unique(hh_4_final))


# household 5
hh_5 <- crossing('A', hh, hh2=hh, hh3=hh, hh4=hh) %>% mutate(compos = paste0('A', hh, hh2, hh3, hh4 ))
length(unique(hh_5$compos))


hh_5_final <- vapply(strsplit(hh_5$compos, NULL), function(x) paste(sort(x), collapse = ''), '')
length(unique(hh_5_final))
#
#
#unique

unique_hh1 <- c("A")
unique_hh2 <- unique(hh_2$compos)
unique_hh3 <- unique(hh_3_final)
unique_hh4 <- unique(hh_4_final)
unique_hh5 <- unique(hh_5_final)


comm_0 <- data.frame(compos = c(unique_hh1, unique_hh2, unique_hh3, unique_hh4, unique_hh5))


comm_1 <- comm_0 %>% separate(compos, c("A", "B", "C", "D", "E"), sep = )


comm_sub <- comm_0 %>% mutate(cat_per1 = substr(compos,1,1),
                              cat_per2 = substr(compos,2,2),
                              cat_per3 = substr(compos,3,3),
                              cat_per4 = substr(compos,4,4),
                              cat_per5 = substr(compos,5,5)
)


comm_sub2 <- comm_sub %>% select(cat_per1, cat_per2, cat_per3, cat_per4, cat_per5) %>% rowwise() #%>% summarise(adul = count('A'))

#count adults
comm_sub2 <- comm_sub2 %>% mutate(adults_per1 = case_when( cat_per1 == "A"  ~ 1),
                                  adults_per2 = case_when( cat_per2 == "A"  ~ 1),
                                  adults_per3 = case_when( cat_per3 == "A"  ~ 1),
                                  adults_per4 = case_when( cat_per4 == "A"  ~ 1),
                                  adults_per5 = case_when( cat_per5 == "A"  ~ 1),
) %>%  rowwise()  %>% mutate(adult = sum(adults_per1, adults_per2, adults_per3, adults_per4, adults_per5, na.rm = TRUE)) %>% select(-c(
  adults_per1,
  adults_per2,
  adults_per3,
  adults_per4,
  adults_per5))

#count teenaagers
comm_sub2 <- comm_sub2 %>% mutate(teenager_per1 = case_when( cat_per1 == "T"  ~ 1),
                                  teenager_per2 = case_when( cat_per2 == "T"  ~ 1),
                                  teenager_per3 = case_when( cat_per3 == "T"  ~ 1),
                                  teenager_per4 = case_when( cat_per4 == "T"  ~ 1),
                                  teenager_per5 = case_when( cat_per5 == "T"  ~ 1),
) %>%  rowwise()  %>% mutate(teenager = sum(teenager_per1, teenager_per2, teenager_per3, teenager_per4, teenager_per5, na.rm = TRUE)) %>% select(-c(teenager_per1,
                                                                                                                                                    teenager_per2,
                                                                                                                                                    teenager_per3,
                                                                                                                                                    teenager_per4,
                                                                                                                                                    teenager_per5))

#count schoolers
comm_sub2 <- comm_sub2 %>% mutate(schooler_per1 = case_when( cat_per1 == "S"  ~ 1),
                                  schooler_per2 = case_when( cat_per2 == "S"  ~ 1),
                                  schooler_per3 = case_when( cat_per3 == "S"  ~ 1),
                                  schooler_per4 = case_when( cat_per4 == "S"  ~ 1),
                                  schooler_per5 = case_when( cat_per5 == "S"  ~ 1),
) %>%  rowwise()  %>% mutate(schooler = sum(schooler_per1, schooler_per2, schooler_per3, schooler_per4, schooler_per5, na.rm = TRUE)) %>% select(-c(schooler_per1,
                                                                                                                                                    schooler_per2,
                                                                                                                                                    schooler_per3,
                                                                                                                                                    schooler_per4,
                                                                                                                                                    schooler_per5))


#count infant
comm_sub2 <- comm_sub2 %>% mutate(infant_per1 = case_when( cat_per1 == "I"  ~ 1),
                                  infant_per2 = case_when( cat_per2 == "I"  ~ 1),
                                  infant_per3 = case_when( cat_per3 == "I"  ~ 1),
                                  infant_per4 = case_when( cat_per4 == "I"  ~ 1),
                                  infant_per5 = case_when( cat_per5 == "I"  ~ 1),
) %>%  rowwise()  %>% mutate(infant = sum(infant_per1, infant_per2, infant_per3, infant_per4, infant_per5, na.rm = TRUE)) %>% select(-c(infant_per1,
                                                                                                                                        infant_per2,
                                                                                                                                        infant_per3,
                                                                                                                                        infant_per4,
                                                                                                                                        infant_per5))

#total members: community all possibilities
hh_config_all_poss_init <- comm_sub2 %>%  rowwise()  %>% mutate(hh_size = sum(adult, teenager, schooler, infant) )

#IDENTIFIER household composition
q1 <- hh_config_all_poss_init %>% mutate(hh_compos = paste0(adult, teenager, schooler, 0, 0, infant),
                                         preschooler = 0,
                                         toddler = 0)

### specify age
q1 <-  q1 %>% mutate(per1 = case_when( cat_per1 == "A"  ~ 35,
                                       cat_per1 == "T"  ~ 15,
                                       cat_per1 == "S"  ~ 10,
                                       cat_per1 == "I"  ~ 1),
                     per2 = case_when( cat_per2 == "A"  ~ 35,
                                       cat_per2 == "T"  ~ 15,
                                       cat_per2 == "S"  ~ 10,
                                       cat_per2 == "I"  ~ 1),
                     per3 = case_when( cat_per3 == "A"  ~ 35,
                                       cat_per3 == "T"  ~ 15,
                                       cat_per3 == "S"  ~ 10,
                                       cat_per3 == "I"  ~ 1), 
                     per4 = case_when( cat_per4 == "A"  ~ 35,
                                       cat_per4 == "T"  ~ 15,
                                       cat_per4 == "S"  ~ 10,
                                       cat_per4 == "I"  ~ 1),
                     per5 = case_when( cat_per5 == "A"  ~ 35,
                                       cat_per5 == "T"  ~ 15,
                                       cat_per5 == "S"  ~ 10,
                                       cat_per5 == "I"  ~ 1)
)

####


#income categories
income_reference <- data.frame(income_cat=c('Less than $15,000',
                                            '$15,000 to $24,999',              
                                            '$25,000 to $34,999',
                                            '$35,000 to $49,999',
                                            '$50,000 to $74,999',
                                            '$75,000 to $99,999',
                                            '$100,000 to $149,999',
                                            '$150,000 to $199,999',
                                            '$200,000 or more')
                               , hhincome = c(
                                 7500, 
                                 20000, 
                                 30000, 
                                 42500, 
                                 62500, 
                                 87500, 
                                 125000, 
                                 175000, 
                                 225000 
                               )
)

#combinations hh_config and income categories
q1_income <- crossing(q1, income_reference)
q1_income <- q1_income %>% mutate(id_fam = row_number())

#geographical 
list_puma <- c(59301, 59302, 59303, 59304, 59305, 59306, 59307, 59308, 59309)

q1_income_puma <- crossing(list_puma, q1_income)

#create id = SERIAL
q1_income_puma <- q1_income_puma %>% mutate(SERIAL = paste0(row_number(), 'a'))



#source https://www.census.gov/programs-surveys/geography/guidance/geo-areas/pumas.html
#source tallies https://www2.census.gov/geo/docs/maps-data/data/geo_tallies2020/tallies_by_state/Virginia_51.txt 
puma_ct <- read_delim("~/git/cost-living/data/crosswalks/2010_Census_Tract_to_2010_PUMA.txt", delim = ",")
puma_ct_20 <- read_delim("~/git/cost-living/data/crosswalks/2020_Census_Tract_to_2020_PUMA.txt", delim = ",")

# crosswalk for Fairfax County only
puma_ct_fairfax <- puma_ct %>% filter(STATEFP=='51', COUNTYFP== '059')

#puma_ct_fairfax_20 <- puma_ct_20 %>% filter(STATEFP=='51', COUNTYFP== '059')

puma_ct_fairfax_20_county <- puma_ct_20 %>% filter(STATEFP=='51', COUNTYFP== '059')
puma_ct_fairfax_20_city <- puma_ct_20 %>% filter(STATEFP=='51', COUNTYFP== '610')
puma_ct_fairfax_20_fallschurch <- puma_ct_20 %>% filter(STATEFP=='51', COUNTYFP== '600')

puma_ct_fairfax_20 <- rbind(puma_ct_fairfax_20_county, puma_ct_fairfax_20_city, puma_ct_fairfax_20_fallschurch)

#puma_ct_fairfax_2 <- puma_ct_fairfax %>% head(2)
puma_ct_fairfax$fips <- paste0(puma_ct_fairfax$STATEFP, puma_ct_fairfax$COUNTYFP, puma_ct_fairfax$TRACTCE )
puma_ct_fairfax_20$fips <- paste0(puma_ct_fairfax_20$STATEFP, puma_ct_fairfax_20$COUNTYFP, puma_ct_fairfax_20$TRACTCE )

#comparison
compare_puma_ct <- puma_ct_fairfax_20 %>% left_join(puma_ct_fairfax, by='fips')
table(compare_puma_ct$PUMA5CE.x, compare_puma_ct$PUMA5CE.y)
equivalence <-  compare_puma_ct %>% group_by(PUMA5CE.x) %>% summarise(equiv=first(PUMA5CE.y))

#rewrite categories of puma_ct_fairfax_20 (274 tracts) to match puma_ct_fairfax (258 tracts)
names(puma_ct_fairfax_20)[4] <- 'PUMA5CE_20'

puma_ct_fairfax_20 <- puma_ct_fairfax_20 %>% mutate(PUMA5CE= case_when(PUMA5CE_20 == '05901' ~ '59309',
                                                                       PUMA5CE_20 == '05902' ~ '59307', 
                                                                       PUMA5CE_20 == '05904' ~ '59305', 
                                                                       PUMA5CE_20 == '05905' ~ '59304', 
                                                                       PUMA5CE_20 == '05906' ~ '59306', 
                                                                       PUMA5CE_20 == '05907' ~ '59301', 
                                                                       PUMA5CE_20 == '05908' ~ '59302', 
                                                                       PUMA5CE_20 == '60001' ~ '59303', 
                                                                       PUMA5CE_20 == '61001' ~ '59308'
) )


#Data
#df_hh_model <- read_csv("~/git/cost-living/code/cost_of_living_budget/1_general_model_col/hh_age_composition_insurance_marst.csv")

df_hh <- q1_income_puma

#HINSEMP 
# HINSEMP   Health insurance through employer/union
# 1          No insurance through employer/union
# 2          Has insurance through employer/union

df_hh_indiv_insur <- df_hh ## %>% filter(HINSEMP == 1)

#df_hh_indiv_insur %>% group_by(income_cat) %>% summarise(tot = sum(hh_num))

#7 steps to estimate healthcare cost for individual plans (no through employer)
#1 Percentage FPL

### Estimation WITH Premium Tax Credit -  TO BE REVISED
#federal poverty line FPL

FPL = c(12880,  17420,  21960, 26500, 31040, 35580, 40120, 44660 )
#Source: https://www.healthreformbeyondthebasics.org/wp-content/uploads/2021/09/REFERENCE-GUIDE_Yearly-Guideline-and-Thresholds_CoverageYear2022-1.pdf

df_hh_indiv_insur <- df_hh_indiv_insur %>% mutate(num_pax = adult + preschooler + toddler + schooler + teenager + infant) %>% 
  mutate(fpl_factor = case_when( num_pax == 1 ~ hhincome/FPL[1]*100,
                                 num_pax == 2 ~ hhincome/FPL[2]*100,
                                 num_pax == 3 ~ hhincome/FPL[3]*100,
                                 num_pax == 4 ~ hhincome/FPL[4]*100,
                                 num_pax == 5 ~ hhincome/FPL[5]*100,
                                 num_pax == 6 ~ hhincome/FPL[6]*100,
                                 num_pax == 7 ~ hhincome/FPL[7]*100,
                                 num_pax >= 8 ~ hhincome/FPL[8]*100
  )
  ) 

df_hh_indiv_insur$fpl_factor <- round(df_hh_indiv_insur$fpl_factor,0)                                                 

#2 Expected percentage
#table from IRS
form_irs_8692 <- read_excel("~/git/cost-living/data/healthcare_cost_marketplace/table_form_8962.xlsx")

df_hh_indiv_insur <- df_hh_indiv_insur %>% left_join(form_irs_8692, by = c("fpl_factor"="fpl_threshold") ) %>% 
  mutate(expected_pctage = case_when( 
    fpl_factor <= 150 ~ 0,
    fpl_factor >= 400 ~ 0.085, 
    fpl_factor > 150 & fpl_factor < 400 ~ expected_pc
  ))


#3 Expected year contribution
df_hh_indiv_insur <- df_hh_indiv_insur %>% mutate(exp_year_contrib = expected_pctage*hhincome, 
                                                  exp_year_contrib_month = exp_year_contrib/12 )


#4 Benchmark plan (SLCSP)
library(readxl)
premium_costs_mktplace <- read_excel("~/git/cost-living/data/healthcare_cost_marketplace/Individual_Market_Medical.xlsx", skip = 1)
#https://www.healthcare.gov/health-plan-information-2022/


# premium_costs_mktplace_va <- premium_costs_mktplace %>% 
#   filter(`State Code` == 'VA')

#write_csv(premium_costs_mktplace_va, "~/git/cost-living/data/healthcare_cost_marketplace/Individual_Market_Medical_VA.xlsx")

premium_costs_mktplace_geospecific <- premium_costs_mktplace %>% 
  filter(`State Code` == 'VA') %>% 
  filter(`County Name` == 'Fairfax') %>% 
  filter( `Rating Area` == 'Rating Area 10') %>%
  filter(`Metal Level` == 'Silver') %>% 
  select(
    "State Code",
    "FIPS County Code",
    "County Name",
    "Rating Area",
    "Metal Level",
    "Plan Marketing Name",
    "Rating Area",
    "Premium Child Age 0-14",
    "Premium Child Age 18", 
    "Premium Adult Individual Age 21",
    "Premium Adult Individual Age 27", 
    "Premium Adult Individual Age 30",
    "Premium Adult Individual Age 40",
    "Premium Adult Individual Age 50",
    "Premium Adult Individual Age 60"
  ) %>% arrange(`Premium Adult Individual Age 30`) %>% 
  slice(2)

#calculate the benchmark individual plans
df_hh_indiv_insur <- df_hh_indiv_insur %>% 
  mutate(plan1 = case_when(per1 <= 14 ~ premium_costs_mktplace_geospecific$`Premium Child Age 0-14`,
                           per1 > 14 & per1 <= 18 ~ premium_costs_mktplace_geospecific$`Premium Child Age 18`,
                           per1 > 18 & per1 <= 21 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 21`,
                           per1 > 21 & per1 <= 27 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 27`,
                           per1 > 27 & per1 <= 30 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 30`,
                           per1 > 30 & per1 <= 40 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 40`,
                           per1 > 40 & per1 <= 50 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 50`,
                           per1 > 50  ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 60`),
         
         plan2 = case_when(per2 <= 14 ~ premium_costs_mktplace_geospecific$`Premium Child Age 0-14`,
                           per2 > 14 & per2 <= 18 ~ premium_costs_mktplace_geospecific$`Premium Child Age 18`,
                           per2 > 18 & per2 <= 21 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 21`,
                           per2 > 21 & per2 <= 27 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 27`,
                           per2 > 27 & per2 <= 30 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 30`,
                           per2 > 30 & per2 <= 40 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 40`,
                           per2 > 40 & per2 <= 50 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 50`,
                           per2 > 50  ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 60`),
         
         plan3 = case_when(per3 <= 14 ~ premium_costs_mktplace_geospecific$`Premium Child Age 0-14`,
                           per3 > 14 & per3 <= 18 ~ premium_costs_mktplace_geospecific$`Premium Child Age 18`,
                           per3 > 18 & per3 <= 21 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 21`,
                           per3 > 21 & per3 <= 27 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 27`,
                           per3 > 27 & per3 <= 30 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 30`,
                           per3 > 30 & per3 <= 40 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 40`,
                           per3 > 40 & per3 <= 50 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 50`,
                           per3 > 50  ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 60`),
         
         plan4 = case_when(per4 <= 14 ~ premium_costs_mktplace_geospecific$`Premium Child Age 0-14`,
                           per4 > 14 & per4 <= 18 ~ premium_costs_mktplace_geospecific$`Premium Child Age 18`,
                           per4 > 18 & per4 <= 21 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 21`,
                           per4 > 21 & per4 <= 27 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 27`,
                           per4 > 27 & per4 <= 30 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 30`,
                           per4 > 30 & per4 <= 40 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 40`,
                           per4 > 40 & per4 <= 50 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 50`,
                           per4 > 50  ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 60`),
         
         plan5 = case_when(per5 <= 14 ~ premium_costs_mktplace_geospecific$`Premium Child Age 0-14`,
                           per5 > 14 & per5 <= 18 ~ premium_costs_mktplace_geospecific$`Premium Child Age 18`,
                           per5 > 18 & per5 <= 21 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 21`,
                           per5 > 21 & per5 <= 27 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 27`,
                           per5 > 27 & per5 <= 30 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 30`,
                           per5 > 30 & per5 <= 40 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 40`,
                           per5 > 40 & per5 <= 50 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 50`,
                           per5 > 50  ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 60`)
         # ,
         # 
         # plan6 = case_when(per6 <= 14 ~ premium_costs_mktplace_geospecific$`Premium Child Age 0-14`,
         #                   per6 > 14 & per6 <= 18 ~ premium_costs_mktplace_geospecific$`Premium Child Age 18`,
         #                   per6 > 18 & per6 <= 21 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 21`,
         #                   per6 > 21 & per6 <= 27 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 27`,
         #                   per6 > 27 & per6 <= 30 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 30`,
         #                   per6 > 30 & per6 <= 40 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 40`,
         #                   per6 > 40 & per6 <= 50 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 50`,
         #                   per6 > 50  ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 60`),
         # 
         # plan7 = case_when(per7 <= 14 ~ premium_costs_mktplace_geospecific$`Premium Child Age 0-14`,
         #                   per7 > 14 & per7 <= 18 ~ premium_costs_mktplace_geospecific$`Premium Child Age 18`,
         #                   per7 > 18 & per7 <= 21 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 21`,
         #                   per7 > 21 & per7 <= 27 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 27`,
         #                   per7 > 27 & per7 <= 30 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 30`,
         #                   per7 > 30 & per7 <= 40 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 40`,
         #                   per7 > 40 & per7 <= 50 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 50`,
         #                   per7 > 50  ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 60`),
         # 
         # plan8 = case_when(per8 <= 14 ~ premium_costs_mktplace_geospecific$`Premium Child Age 0-14`,
         #                   per8 > 14 & per8 <= 18 ~ premium_costs_mktplace_geospecific$`Premium Child Age 18`,
         #                   per8 > 18 & per8 <= 21 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 21`,
         #                   per8 > 21 & per8 <= 27 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 27`,
         #                   per8 > 27 & per8 <= 30 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 30`,
         #                   per8 > 30 & per8 <= 40 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 40`,
         #                   per8 > 40 & per8 <= 50 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 50`,
         #                   per8 > 50  ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 60`), 
         # 
         # plan9 = case_when(per9 <= 14 ~ premium_costs_mktplace_geospecific$`Premium Child Age 0-14`,
         #                   per9 > 14 & per9 <= 18 ~ premium_costs_mktplace_geospecific$`Premium Child Age 18`,
         #                   per9 > 18 & per9 <= 21 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 21`,
         #                   per9 > 21 & per9 <= 27 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 27`,
         #                   per9 > 27 & per9 <= 30 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 30`,
         #                   per9 > 30 & per9 <= 40 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 40`,
         #                   per9 > 40 & per9 <= 50 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 50`,
         #                   per9 > 50  ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 60`),
         # 
         # plan10 = case_when(per10 <= 14 ~ premium_costs_mktplace_geospecific$`Premium Child Age 0-14`,
         #                   per10 > 14 & per10 <= 18 ~ premium_costs_mktplace_geospecific$`Premium Child Age 18`,
         #                   per10 > 18 & per10 <= 21 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 21`,
         #                   per10 > 21 & per10 <= 27 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 27`,
         #                   per10 > 27 & per10 <= 30 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 30`,
         #                   per10 > 30 & per10 <= 40 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 40`,
         #                   per10 > 40 & per10 <= 50 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 50`,
         #                   per10 > 50  ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 60`),
         # 
         # plan11 = case_when(per11 <= 14 ~ premium_costs_mktplace_geospecific$`Premium Child Age 0-14`,
         #                   per11 > 14 & per11 <= 18 ~ premium_costs_mktplace_geospecific$`Premium Child Age 18`,
         #                   per11 > 18 & per11 <= 21 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 21`,
         #                   per11 > 21 & per11 <= 27 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 27`,
         #                   per11 > 27 & per11 <= 30 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 30`,
         #                   per11 > 30 & per11 <= 40 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 40`,
         #                   per11 > 40 & per11 <= 50 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 50`,
         #                   per11 > 50  ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 60`),
         # 
         # plan12 = case_when(per12 <= 14 ~ premium_costs_mktplace_geospecific$`Premium Child Age 0-14`,
         #                   per12 > 14 & per12 <= 18 ~ premium_costs_mktplace_geospecific$`Premium Child Age 18`,
         #                   per12 > 18 & per12 <= 21 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 21`,
         #                   per12 > 21 & per12 <= 27 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 27`,
         #                   per12 > 27 & per12 <= 30 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 30`,
         #                   per12 > 30 & per12 <= 40 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 40`,
         #                   per12 > 40 & per12 <= 50 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 50`,
         #                   per12 > 50  ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 60`),
         # 
         # plan13 = case_when(per13 <= 14 ~ premium_costs_mktplace_geospecific$`Premium Child Age 0-14`,
         #                   per13 > 14 & per13 <= 18 ~ premium_costs_mktplace_geospecific$`Premium Child Age 18`,
         #                   per13 > 18 & per13 <= 21 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 21`,
         #                   per13 > 21 & per13 <= 27 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 27`,
         #                   per13 > 27 & per13 <= 30 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 30`,
         #                   per13 > 30 & per13 <= 40 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 40`,
         #                   per13 > 40 & per13 <= 50 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 50`,
         #                   per13 > 50  ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 60`),
         # 
         # plan14 = case_when(per14 <= 14 ~ premium_costs_mktplace_geospecific$`Premium Child Age 0-14`,
         #                   per14 > 14 & per14 <= 18 ~ premium_costs_mktplace_geospecific$`Premium Child Age 18`,
         #                   per14 > 18 & per14 <= 21 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 21`,
         #                   per14 > 21 & per14 <= 27 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 27`,
         #                   per14 > 27 & per14 <= 30 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 30`,
         #                   per14 > 30 & per14 <= 40 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 40`,
         #                   per14 > 40 & per14 <= 50 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 50`,
         #                   per14 > 50  ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 60`),
         # 
         # plan15 = case_when(per15 <= 14 ~ premium_costs_mktplace_geospecific$`Premium Child Age 0-14`,
         #                   per15 > 14 & per15 <= 18 ~ premium_costs_mktplace_geospecific$`Premium Child Age 18`,
         #                   per15 > 18 & per15 <= 21 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 21`,
         #                   per15 > 21 & per15 <= 27 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 27`,
         #                   per15 > 27 & per15 <= 30 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 30`,
         #                   per15 > 30 & per15 <= 40 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 40`,
         #                   per15 > 40 & per15 <= 50 ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 50`,
         #                   per15 > 50  ~ premium_costs_mktplace_geospecific$`Premium Adult Individual Age 60`)
         
  )

#benchmark plan
df_hh_indiv_insur <- df_hh_indiv_insur %>% mutate(benchmark_plan = rowSums(df_hh_indiv_insur[, which(names(df_hh_indiv_insur) == "plan1") : which(names(df_hh_indiv_insur) == "plan5")], na.rm=TRUE) )

#5 Premium Tax Credit
df_hh_indiv_insur <- df_hh_indiv_insur %>% mutate(ptc = ifelse(benchmark_plan < exp_year_contrib_month, 0,  benchmark_plan - exp_year_contrib_month ) ) 

#6 Premium = Cost - ptc
#cost with the lowest bronze
costs_mktplace_lowest_bronze <- premium_costs_mktplace %>% 
  filter(`State Code` == 'VA') %>% 
  filter(`County Name` == 'Fairfax') %>% 
  filter( `Rating Area` == 'Rating Area 10') %>%
  filter(`Metal Level` == 'Bronze') %>% 
  select(
    "State Code",
    "FIPS County Code",
    "County Name",
    "Rating Area",
    "Metal Level",
    "Plan Marketing Name",
    "Rating Area",
    "Premium Child Age 0-14",
    "Premium Child Age 18", 
    "Premium Adult Individual Age 21",
    "Premium Adult Individual Age 27", 
    "Premium Adult Individual Age 30",
    "Premium Adult Individual Age 40",
    "Premium Adult Individual Age 50",
    "Premium Adult Individual Age 60", 
    "Medical Maximum Out Of Pocket - Individual - Standard",
    "Medical Maximum Out Of Pocket - Family - Standard" 
  ) %>% arrange(`Premium Adult Individual Age 30`) %>% 
  slice_min(`Premium Adult Individual Age 30`)

#cost with the lowest silver
costs_mktplace_lowest_silver <- premium_costs_mktplace %>% 
  filter(`State Code` == 'VA') %>% 
  filter(`County Name` == 'Fairfax') %>% 
  filter( `Rating Area` == 'Rating Area 10') %>%
  filter(`Metal Level` == 'Silver') %>% 
  select(
    "State Code",
    "FIPS County Code",
    "County Name",
    "Rating Area",
    "Metal Level",
    "Plan Marketing Name",
    "Rating Area",
    "Premium Child Age 0-14",
    "Premium Child Age 18", 
    "Premium Adult Individual Age 21",
    "Premium Adult Individual Age 27", 
    "Premium Adult Individual Age 30",
    "Premium Adult Individual Age 40",
    "Premium Adult Individual Age 50",
    "Premium Adult Individual Age 60", 
    "Medical Maximum Out Of Pocket - Individual - Standard",
    "Medical Maximum Out Of Pocket - Family - Standard" 
  ) %>% arrange(`Premium Adult Individual Age 30`) %>% 
  slice_min(`Premium Adult Individual Age 30`)



# costs_mktplace_lowest_bronze
# costs_mktplace_lowest_silver

#estimate cost of plans with lowest bronze
df_hh_indiv_insur <- df_hh_indiv_insur %>% 
  mutate(plan1_bro = case_when(per1 <= 14 ~ costs_mktplace_lowest_bronze$`Premium Child Age 0-14`,
                               per1 > 14 & per1 <= 18 ~ costs_mktplace_lowest_bronze$`Premium Child Age 18`,
                               per1 > 18 & per1 <= 21 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 21`,
                               per1 > 21 & per1 <= 27 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 27`,
                               per1 > 27 & per1 <= 30 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 30`,
                               per1 > 30 & per1 <= 40 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 40`,
                               per1 > 40 & per1 <= 50 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 50`,
                               per1 > 50  ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 60`),
         
         plan2_bro = case_when(per2 <= 14 ~ costs_mktplace_lowest_bronze$`Premium Child Age 0-14`,
                               per2 > 14 & per2 <= 18 ~ costs_mktplace_lowest_bronze$`Premium Child Age 18`,
                               per2 > 18 & per2 <= 21 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 21`,
                               per2 > 21 & per2 <= 27 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 27`,
                               per2 > 27 & per2 <= 30 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 30`,
                               per2 > 30 & per2 <= 40 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 40`,
                               per2 > 40 & per2 <= 50 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 50`,
                               per2 > 50  ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 60`),
         
         plan3_bro = case_when(per3 <= 14 ~ costs_mktplace_lowest_bronze$`Premium Child Age 0-14`,
                               per3 > 14 & per3 <= 18 ~ costs_mktplace_lowest_bronze$`Premium Child Age 18`,
                               per3 > 18 & per3 <= 21 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 21`,
                               per3 > 21 & per3 <= 27 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 27`,
                               per3 > 27 & per3 <= 30 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 30`,
                               per3 > 30 & per3 <= 40 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 40`,
                               per3 > 40 & per3 <= 50 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 50`,
                               per3 > 50  ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 60`),
         
         plan4_bro = case_when(per4 <= 14 ~ costs_mktplace_lowest_bronze$`Premium Child Age 0-14`,
                               per4 > 14 & per4 <= 18 ~ costs_mktplace_lowest_bronze$`Premium Child Age 18`,
                               per4 > 18 & per4 <= 21 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 21`,
                               per4 > 21 & per4 <= 27 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 27`,
                               per4 > 27 & per4 <= 30 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 30`,
                               per4 > 30 & per4 <= 40 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 40`,
                               per4 > 40 & per4 <= 50 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 50`,
                               per4 > 50  ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 60`),
         
         plan5_bro = case_when(per5 <= 14 ~ costs_mktplace_lowest_bronze$`Premium Child Age 0-14`,
                               per5 > 14 & per5 <= 18 ~ costs_mktplace_lowest_bronze$`Premium Child Age 18`,
                               per5 > 18 & per5 <= 21 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 21`,
                               per5 > 21 & per5 <= 27 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 27`,
                               per5 > 27 & per5 <= 30 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 30`,
                               per5 > 30 & per5 <= 40 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 40`,
                               per5 > 40 & per5 <= 50 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 50`,
                               per5 > 50  ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 60`)
         # ,
         # 
         # plan6_bro = case_when(per6 <= 14 ~ costs_mktplace_lowest_bronze$`Premium Child Age 0-14`,
         #                   per6 > 14 & per6 <= 18 ~ costs_mktplace_lowest_bronze$`Premium Child Age 18`,
         #                   per6 > 18 & per6 <= 21 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 21`,
         #                   per6 > 21 & per6 <= 27 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 27`,
         #                   per6 > 27 & per6 <= 30 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 30`,
         #                   per6 > 30 & per6 <= 40 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 40`,
         #                   per6 > 40 & per6 <= 50 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 50`,
         #                   per6 > 50  ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 60`),
         # 
         # plan7_bro = case_when(per7 <= 14 ~ costs_mktplace_lowest_bronze$`Premium Child Age 0-14`,
         #                   per7 > 14 & per7 <= 18 ~ costs_mktplace_lowest_bronze$`Premium Child Age 18`,
         #                   per7 > 18 & per7 <= 21 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 21`,
         #                   per7 > 21 & per7 <= 27 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 27`,
         #                   per7 > 27 & per7 <= 30 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 30`,
         #                   per7 > 30 & per7 <= 40 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 40`,
         #                   per7 > 40 & per7 <= 50 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 50`,
         #                   per7 > 50  ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 60`),
         # 
         # plan8_bro = case_when(per8 <= 14 ~ costs_mktplace_lowest_bronze$`Premium Child Age 0-14`,
         #                   per8 > 14 & per8 <= 18 ~ costs_mktplace_lowest_bronze$`Premium Child Age 18`,
         #                   per8 > 18 & per8 <= 21 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 21`,
         #                   per8 > 21 & per8 <= 27 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 27`,
         #                   per8 > 27 & per8 <= 30 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 30`,
         #                   per8 > 30 & per8 <= 40 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 40`,
         #                   per8 > 40 & per8 <= 50 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 50`,
         #                   per8 > 50  ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 60`), 
         # 
         # plan9_bro = case_when(per9 <= 14 ~ costs_mktplace_lowest_bronze$`Premium Child Age 0-14`,
         #                   per9 > 14 & per9 <= 18 ~ costs_mktplace_lowest_bronze$`Premium Child Age 18`,
         #                   per9 > 18 & per9 <= 21 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 21`,
         #                   per9 > 21 & per9 <= 27 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 27`,
         #                   per9 > 27 & per9 <= 30 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 30`,
         #                   per9 > 30 & per9 <= 40 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 40`,
         #                   per9 > 40 & per9 <= 50 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 50`,
         #                   per9 > 50  ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 60`),
         # 
         # plan10_bro = case_when(per10 <= 14 ~ costs_mktplace_lowest_bronze$`Premium Child Age 0-14`,
         #                   per10 > 14 & per10 <= 18 ~ costs_mktplace_lowest_bronze$`Premium Child Age 18`,
         #                   per10 > 18 & per10 <= 21 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 21`,
         #                   per10 > 21 & per10 <= 27 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 27`,
         #                   per10 > 27 & per10 <= 30 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 30`,
         #                   per10 > 30 & per10 <= 40 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 40`,
         #                   per10 > 40 & per10 <= 50 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 50`,
         #                   per10 > 50  ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 60`),
         # 
         # plan11_bro = case_when(per11 <= 14 ~ costs_mktplace_lowest_bronze$`Premium Child Age 0-14`,
         #                   per11 > 14 & per11 <= 18 ~ costs_mktplace_lowest_bronze$`Premium Child Age 18`,
         #                   per11 > 18 & per11 <= 21 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 21`,
         #                   per11 > 21 & per11 <= 27 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 27`,
         #                   per11 > 27 & per11 <= 30 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 30`,
         #                   per11 > 30 & per11 <= 40 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 40`,
         #                   per11 > 40 & per11 <= 50 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 50`,
         #                   per11 > 50  ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 60`),
         # 
         # plan12_bro = case_when(per12 <= 14 ~ costs_mktplace_lowest_bronze$`Premium Child Age 0-14`,
         #                   per12 > 14 & per12 <= 18 ~ costs_mktplace_lowest_bronze$`Premium Child Age 18`,
         #                   per12 > 18 & per12 <= 21 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 21`,
         #                   per12 > 21 & per12 <= 27 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 27`,
         #                   per12 > 27 & per12 <= 30 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 30`,
         #                   per12 > 30 & per12 <= 40 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 40`,
         #                   per12 > 40 & per12 <= 50 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 50`,
         #                   per12 > 50  ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 60`),
         # 
         # plan13_bro = case_when(per13 <= 14 ~ costs_mktplace_lowest_bronze$`Premium Child Age 0-14`,
         #                   per13 > 14 & per13 <= 18 ~ costs_mktplace_lowest_bronze$`Premium Child Age 18`,
         #                   per13 > 18 & per13 <= 21 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 21`,
         #                   per13 > 21 & per13 <= 27 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 27`,
         #                   per13 > 27 & per13 <= 30 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 30`,
         #                   per13 > 30 & per13 <= 40 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 40`,
         #                   per13 > 40 & per13 <= 50 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 50`,
         #                   per13 > 50  ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 60`),
         # 
         # plan14_bro = case_when(per14 <= 14 ~ costs_mktplace_lowest_bronze$`Premium Child Age 0-14`,
         #                   per14 > 14 & per14 <= 18 ~ costs_mktplace_lowest_bronze$`Premium Child Age 18`,
         #                   per14 > 18 & per14 <= 21 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 21`,
         #                   per14 > 21 & per14 <= 27 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 27`,
         #                   per14 > 27 & per14 <= 30 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 30`,
         #                   per14 > 30 & per14 <= 40 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 40`,
         #                   per14 > 40 & per14 <= 50 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 50`,
         #                   per14 > 50  ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 60`),
         # 
         # plan15_bro = case_when(per15 <= 14 ~ costs_mktplace_lowest_bronze$`Premium Child Age 0-14`,
         #                   per15 > 14 & per15 <= 18 ~ costs_mktplace_lowest_bronze$`Premium Child Age 18`,
         #                   per15 > 18 & per15 <= 21 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 21`,
         #                   per15 > 21 & per15 <= 27 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 27`,
         #                   per15 > 27 & per15 <= 30 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 30`,
         #                   per15 > 30 & per15 <= 40 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 40`,
         #                   per15 > 40 & per15 <= 50 ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 50`,
         #                   per15 > 50  ~ costs_mktplace_lowest_bronze$`Premium Adult Individual Age 60`)
         
  )

#cost of bronze plan
df_hh_indiv_insur <- df_hh_indiv_insur %>% mutate(cost_bronze_plan = rowSums(df_hh_indiv_insur[, which(names(df_hh_indiv_insur) == "plan1_bro") : which(names(df_hh_indiv_insur) == "plan5_bro")], na.rm=TRUE) )

#determine premium
df_hh_indiv_insur <- df_hh_indiv_insur %>% mutate(premium_month = ifelse( cost_bronze_plan < ptc, 0, cost_bronze_plan - ptc )   )
df_hh_indiv_insur <- df_hh_indiv_insur %>% mutate(premium_month2 = cost_bronze_plan - ptc)

#plot(df_hh_indiv_insur$premium_month, df_hh_indiv_insur$hhincome)

##########################
#7 Yearly Cost - with factor
#data for factors
premium_healthcare <- read_excel("~/git/cost-living/data/healthcare_cost_marketplace/70_healthcare_costs_annual_rep_community.xlsx", sheet = "data_complete")

#annual premium
premium_healthcare <- premium_healthcare %>% mutate(premium_year = ifelse( premium < 0, 0, premium*12 ))

#annual proportion
premium_healthcare <- premium_healthcare %>% mutate(cost_increase_factor =  `yearly cost`/premium_year )

#factors by pieces
factors <- premium_healthcare %>% group_by(income, hh_size, adult) %>% summarise(factor = mean(cost_increase_factor, na.rm = TRUE))

#percentage diff/out-pocket
premium_healthcare <- premium_healthcare %>% mutate(prop_diff =  (`yearly cost`- premium_year)/`max outpock` )

#proportion diff vs out-pocket with
#factors_prop_diff <- premium_healthcare %>% group_by(income, hh_size, adult) %>% summarise(factor = mean(prop_diff, na.rm = TRUE))
factors_prop_diff_hh_size <- premium_healthcare %>% group_by(income, hh_size) %>% summarise(factor = mean(prop_diff, na.rm = TRUE))

factors_prop_diff_hh_size <- factors_prop_diff_hh_size %>% mutate(income_cat = case_when(income == 7500 ~ 'Less than $15,000',
                                                                                         income == 20000 ~ '$15,000 to $24,999',
                                                                                         income == 30000 ~ '$25,000 to $34,999',
                                                                                         income == 42500 ~ '$35,000 to $49,999',
                                                                                         income == 62500 ~ '$50,000 to $74,999',
                                                                                         income == 87500 ~ '$75,000 to $99,999',
                                                                                         income == 125000 ~ '$100,000 to $149,999',
                                                                                         income == 175000 ~ '$150,000 to $199,999',
                                                                                         income == 225000 ~ '$200,000 or more'
))
##################

#assign proportions to estimate yearly costs
df_hh_indiv_insur <- df_hh_indiv_insur %>% left_join(factors_prop_diff_hh_size %>% select(-c(income)), by= c("income_cat", "hh_size"))
#plot(df_hh_indiv_insur$hhincome, df_hh_indiv_insur$factor)

#assign max out-of-pocket
df_hh_indiv_insur <- df_hh_indiv_insur %>% mutate(max_out_pocket = ifelse( hh_size == 1, costs_mktplace_lowest_bronze$`Medical Maximum Out Of Pocket - Individual - Standard`, costs_mktplace_lowest_bronze$`Medical Maximum Out Of Pocket - Family - Standard`) )

df_hh_indiv_insur$max_out_pocket <-  gsub("\\$","", as.character(df_hh_indiv_insur$max_out_pocket))
df_hh_indiv_insur$max_out_pocket <-  gsub(",","", as.character(df_hh_indiv_insur$max_out_pocket))

df_hh_indiv_insur$max_out_pocket_format <- as.numeric(df_hh_indiv_insur$max_out_pocket)

#df_hh_indiv_insur$maxoop <- df_hh_indiv_insur$factor*as.numeric(df_hh_indiv_insur$max_out_pocket)

#yearly costs :  premium_month*12 + out_of_pocket_max*factor. (factor based on low usage)
df_hh_indiv_insur <- df_hh_indiv_insur %>% mutate(yearly_costs_init = premium_month*12 + factor*as.numeric(max_out_pocket), 
                                                  yearly_costs_month_init =yearly_costs_init/12 )

#adjustment for poorest cases, with possible medicaid or CHIP
min_health_month <- df_hh_indiv_insur %>% group_by(hh_size) %>% summarise( min_health_month = min(yearly_costs_month_init, na.rm = TRUE))

#final yearly cost with adjustment for poor
df_hh_indiv_insur <- df_hh_indiv_insur %>% mutate(yearly_costs =  case_when( is.na(yearly_costs_init) & hh_size==1  ~  as.numeric(min_health_month[1, 2]),
                                                                             is.na(yearly_costs_init) & hh_size==2  ~  as.numeric(min_health_month[2, 2]),
                                                                             is.na(yearly_costs_init) & hh_size==3  ~  as.numeric(min_health_month[3, 2]),
                                                                             is.na(yearly_costs_init) & hh_size==4  ~  as.numeric(min_health_month[4, 2]),
                                                                             is.na(yearly_costs_init) & hh_size==5  ~  as.numeric(min_health_month[5 , 2]),
                                                                             !is.na(yearly_costs_init) ~ yearly_costs_init
) ) %>% mutate(yearly_costs_month =  yearly_costs/12)


# min(df_hh_indiv_insur$yearly_costs_month, na.rm = TRUE)
# min_health_year <- min_health_month*12

#assumption: all buy individuals plans, not sponsored by employer
df_hh_indiv_insur <- df_hh_indiv_insur %>% mutate(HINSEMP= 1)

#### cost for employer sponsored
df_hh_indiv_insur <- df_hh_indiv_insur %>% mutate(contrib_worker_month = case_when( HINSEMP == 1 ~  cost_bronze_plan*0.17,
                                                                                    HINSEMP == 2 ~  cost_bronze_plan*0.28
) )

single_plan_sponsored_max_out_pocket <- 4594
family_plan_sponsored_max_out_pocket <- 8375

#health insurance with employer: contribution_month*12 + percentage of Max Out-of-pocket.
#na is lowest income cases.  medicaid potentially.  we assume they have to pay the yearly_costs in case of healthmarketplace
# df_hh_indiv_insur <- df_hh_indiv_insur %>% mutate(health_insur_with_employer_year = case_when(hh_recode == 1 & !is.na(factor) ~ contrib_worker_month*12 + factor*single_plan_sponsored_max_out_pocket,
#                                                                                               hh_recode != 1 & !is.na(factor) ~ contrib_worker_month*12 + factor*family_plan_sponsored_max_out_pocket, 
#                                                                                               is.na(factor) ~ yearly_costs
#                                                                                               ) )

df_hh_indiv_insur <- df_hh_indiv_insur %>% mutate(health_insur_with_employer_year = case_when(hh_size == 1 & !is.na(factor) ~ contrib_worker_month*12 + factor*as.numeric(max_out_pocket),
                                                                                              hh_size != 1 & !is.na(factor) ~ contrib_worker_month*12 + factor*as.numeric(max_out_pocket), 
                                                                                              is.na(factor) ~ yearly_costs
) )


#final estimation: 
#for employer sponsored: %*contrib + % average Out-of-Pocket
#for individual plans: healthcare marketplace

df_hh_indiv_insur <- df_hh_indiv_insur %>% mutate( healthcare_cost_month = case_when(HINSEMP == 1 ~ yearly_costs/12,
                                                                                     HINSEMP == 2 ~ health_insur_with_employer_year/12)
)


# hist(df_hh_indiv_insur$health_insur_with_employer_year)
hist(df_hh_indiv_insur$healthcare_cost_month)
# plot(df_hh_indiv_insur$hhincome, df_hh_indiv_insur$healthcare_cost_month)
# df_hh_indiv_insur %>% group_by(HINSEMP) %>% summarise(mean= weighted.mean(healthcare_cost_month, hh_num))
# t.test(df_hh_indiv_insur %>% filter(HINSEMP==1) %>% select(healthcare_cost_month) ,  df_hh_indiv_insur %>% filter(HINSEMP==2) %>% select(healthcare_cost_month))