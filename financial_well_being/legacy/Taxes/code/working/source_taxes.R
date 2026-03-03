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



# #data(taxpayer_finances)
# taxpayer_finances <- q1_income %>% select(per1, per2, per3, per4, per5, pwages=hhincome, hh_size, adult, teenager , schooler, infant)
# 
# taxpayer_finances <- taxpayer_finances %>% mutate(taxsimid = row_number(), 
#                                                   year = 2022,
#                                                   mstat = case_when(adult == 1 & hh_size == 1 ~ 'single',
#                                                                     adult == 1 & hh_size > 1 ~ 'head of household',
#                                                                     adult >= 2 ~ 'married, jointly'
#                                                                      ), 
#                                                   state = 'Virginia', 
#                                                   page = per1,
#                                                   sage = case_when(per2 == 35 ~ 35),
#                                                   age1 = case_when(per2 == 1 ~ 1,
#                                                                    per2 == 10 ~ 10,
#                                                                    per2 == 15 ~ 15),
#                                                   age2 = case_when(per3 == 1 ~ 1,
#                                                                    per3 == 10 ~ 10,
#                                                                    per3 == 15 ~ 15),
#                                                   age3 = case_when(per4 == 1 ~ 1,
#                                                                    per4 == 10 ~ 10,
#                                                                    per4 == 15 ~ 15),
#                                                   age4 = case_when(per5 == 1 ~ 1,
#                                                                    per5 == 10 ~ 10,
#                                                                    per5 == 15 ~ 15), 
#                                                   swages = 0,
#                                                   dividends = 0, 
#                                                   intrec = 0, 
#                                                   stcg = 0 ,
#                                                   ltcg = 0, 
#                                                   depx = hh_size - adult
#                                                   )
# 
# taxpayer_finances_format <- taxpayer_finances %>% select(taxsimid,	year,	mstat,	state,	page,	sage,	depx,	age1,	age2,	age3,	pwages,	swages,	dividends,	intrec,	stcg,	ltcg)
# #variables in df
# 
# 
# library(usincometaxes)
# taxsim_dataset <- create_dataset_for_taxsim(taxpayer_finances_format)
# 
# knitr::kable(head(taxsim_dataset))
# 
# 
# #save to send to taxsim
# write_csv(taxsim_dataset, "~/git/cost-living/code/cost_of_living_budget/2_col_theory_version_rep_community/taxsim_dataset_new.csv")


#OPEN after processing income information at taxsim
taxsim_nber <- read_csv("~/git/cost-living/code/cost_of_living_budget/2_col_theory_version_rep_community/taxsim.nber.org_taxsim35_redirect.csv")

taxsim_nber_month <- taxsim_nber %>% select(taxsimid, total_tax) %>% mutate(taxes_month = ifelse(total_tax <0, 0, total_tax/12) ) %>% select( -c(total_tax))