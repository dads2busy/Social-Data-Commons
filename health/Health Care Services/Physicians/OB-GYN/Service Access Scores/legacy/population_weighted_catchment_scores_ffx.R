# getting weighted mean catchment scores for each subpop in fairfax

# Total Female 15-17 B01001_030
# Total Female 18+ B01001_031-049
# Total white female B01001A_022-031
# Total black female B01001B_022-031
# Total native female B01001C_022-031
# Total asian female B01001D_022-031
# Total native hawaiian/other pi B01001E_022-031
# Total other race B01001F_022-031
# Total two or more races B01001G_022-031
# Girls e.g. B01001(A-G)_021
# Total hispanic or latina B01001I_017

library(dplyr)
library(tidycensus)
library(stringr)
library(tidyverse)

census_api_key(Sys.getenv('census_api_key'))

pretty_name <- function(var) {
  race_eth <- c('1'='total', 'A'='white', 'B'='black', 'C'='native', 'D'='asian',
                'E'='native hawaiian or other pacific islander', 'F'='other races',
                'G'='two or more races', 'H'='white non-hispanic', 'I'='hispanic or latino')

  race_eth_code <- stringr::str_sub((str_split_i(var, '_', 1)), -1, -1)
  age_code <- substr(str_split_i(var, '_', 2), 2, 3)

  pretty <- paste(race_eth[[race_eth_code]], 'female',
                  if_else(age_code=='WM', 'ages 18+', 'ages 15-17'))

  return(pretty)
}

get_women_and_girls <- function() {
  # get data on women and girls in fairfax county. age separated 15-17, 18+.
  # contains race intersections

  groups <- sapply(LETTERS[1:9], function(x){paste0('B01001', x, '_0')}, USE.NAMES = FALSE)

  # get adult data
  acs <- NULL
  for (group in groups) {
    vars <- sapply(22:31, function(x){paste0(group, x)})
    temp_acs <- get_acs('tract', variables=vars, year=2021, state="VA",
                        county='Fairfax County') %>%
      select(geoid=GEOID, variable, estimate) %>% group_by(geoid) %>%
      summarise(variable=paste0(group, 'WM'),
                estimate=sum(estimate))

    acs <- rbind(acs, temp_acs)
  }

  # get age 15-17 data
  vars <- sapply(groups, function(x){paste0(x, '21')}, USE.NAMES = FALSE)
  temp_acs <- get_acs('tract', variables=vars, year=2021, state="VA",
                      county='Fairfax County') %>%
    select(geoid=GEOID, variable, estimate)
  acs <- rbind(acs, temp_acs)

  # get total data for women
  vars <- sapply(31:49, function(x){paste0('B01001_0', x)})
  temp_acs <- get_acs('tract', variables=vars, year=2021, state="VA",
                      county='Fairfax County') %>%
    select(geoid=GEOID, variable, estimate) %>% group_by(geoid) %>%
    summarise(variable='B01001_0WM',
              estimate=sum(estimate))
  acs <- rbind(acs, temp_acs)

  # get total data for girls
  temp_acs <- get_acs('tract', variables='B01001_030', year=2021, state="VA",
                      county='Fairfax County') %>%
    select(geoid=GEOID, variable, estimate)
  acs <- rbind(acs, temp_acs)

  return(acs)
}

# get acs data
acs <- get_women_and_girls()

# download access scores
access_scores <- read.csv('~/git/sdc.health_dev/Health Care Services/Physicians/OB-GYN/Service Access Scores/data/distribution/va059_cms_2022_obgyn_access_scores.csv.xz',
                          colClasses = c(geoid='character'))

# filter for ffx and relevant data
access_scores <- access_scores %>%
  filter(startsWith(geoid, '51059'), measure=='obgyn_e2sfca') %>%
  select(geoid, value)

# merge
joined <- left_join(acs, access_scores, by=join_by('geoid')) %>%
  filter(!is.na(value))

# calculate weighted means
weighted <- joined %>% group_by(variable) %>%
  summarise(weighted_mean = weighted.mean(value, estimate)) %>%
  mutate(desc = sapply(variable, pretty_name))

write_csv(weighted, "~/git/sdc.health_dev/Health Care Services/Physicians/OB-GYN/Service Access Scores/data/distribution/va059_weighted_access_scores_obgyn.csv")

## PEDITRICIAN GIRLS

girls_vars <- c(paste0("B01001A_0", seq(18, 21)), 
                     paste0("B01001B_0", seq(18, 21)),
                     paste0("B01001C_0", seq(18, 21)),
                     paste0("B01001D_0", seq(18, 21)),
                     paste0("B01001E_0", seq(18, 21)),
                     paste0("B01001F_0", seq(18, 21)),
                     paste0("B01001G_0", seq(18, 21)),
                     paste0("B01001H_0", seq(18, 21)),
                     paste0("B01001I_0", seq(18, 21)))

acs <- get_acs('tract', variables=girls_vars, year=2021, state="VA",
        county='Fairfax County') %>% select(geoid=GEOID, variable, estimate) %>%
  mutate(desc = case_when(
    str_detect(variable, "A") ~ "white",
    str_detect(variable, "C") ~ "native",
    str_detect(variable, "D") ~ "asian",
    str_detect(variable, "E") ~ "native hawaiian or other pacific islander",
    str_detect(variable, "F") ~ "other races",
    str_detect(variable, "G") ~ "two or more races",
    str_detect(variable, "H") ~ "white non-hispanic",
    str_detect(variable, "I") ~ "hispanic or latino",
    TRUE ~ "black"
  ))

# download access scores
access_scores <- read.csv('~/git/sdc.health_dev/Health Care Services/Physicians/Pediatric/Service Access Scores/data/distribution/va059_webmd_2022_pediatricians_access_scores.csv.xz',
                          colClasses = c(geoid='character'))

# filter for ffx and relevant data
access_scores <- access_scores %>%
  filter(startsWith(geoid, '51059'), measure=='pediatrician_e2sfca') %>%
  select(geoid, value)

# merge
joined <- left_join(acs, access_scores, by=join_by('geoid')) %>%
  filter(!is.na(value))

# calculate weighted means
weighted <- joined %>% group_by(desc) %>%
  summarise(weighted_mean = weighted.mean(value, estimate)) 

write_csv(weighted, "~/git/sdc.health_dev/Health Care Services/Physicians/Pediatric/Service Access Scores/data/distribution/va059_weighted_access_scores_pediatrician.csv")
