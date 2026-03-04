options(scipen=999)
library(tidycensus)
library(tidyr)
library(dplyr)
library(tigris)
library(khroma)
library(tmap)
library(srvyr)
census_api_key("cf02220f463253d826317354efa3abfba13a34a7", overwrite = TRUE, install = TRUE)

View(pums_variables)

fx_pums <- c("59301", "59302", "59303", "59304", "59305", "59306", "59307", "59308", "59309")
fx_vars <- c("HHL", "NATIVITY", "HHLDRHISP", "HICOV", "AGEP", "SEX", "RAC1P", "HISP", 
             "HINS1", "HINS2", "HINS3", "HINS4", "HINS5", "HINS6", "HINS7", "HHT2")


pums_orig <- 
  get_pums(
    variables = fx_vars,
    state = "VA",
    puma = fx_pums,
    year = 2022,  # Changed year to 2023
    survey = "acs5",
    return_vacant = FALSE,
    recode = FALSE,
    #rep_weights = "person"
  ) #%>% to_survey()


# Recode variables: sex, race/ethnicity, age group
fx_pums_df <- pums_orig %>%
  mutate(SEX = ifelse(SEX == 1, 'Male', 'Female'), 
         race_eth = case_when(
           RAC1P == "1" ~ "White",
           RAC1P == "2" ~ "Black",
           RAC1P == "6" ~ "Asian",
           RAC1P == "9" ~ "Two or More",
           RAC1P == "8" ~ "Other",
           TRUE ~ "Native"
         ),
         age_group = case_when(
           AGEP < 18 ~ "Children \n(under 18)",
           AGEP < 65 ~ "Adults (18-64)",
           TRUE ~ "Adults (65+)"
         ))

# Recode variables: sex, ethnicity, and age group for another set of data
fx_pums_df2 <- pums_orig %>%
  mutate(SEX = ifelse(SEX == 1, 'Male', 'Female'), 
         race_eth = case_when(
           HISP != "01" ~ "Hispanic",
           TRUE ~ "Not Hispanic"
         ),
         age_group = case_when(
           AGEP < 18 ~ "Children \n(under 18)",
           AGEP < 65 ~ "Adults (18-64)",
           TRUE ~ "Adults (65+)"
         ))
fx_pums_df <- fx_pums_df %>% bind_rows(fx_pums_df2)

fx_pums_df <- fx_pums_df %>%
  mutate(HICOV = ifelse(HICOV == 1, 1, 0)) %>%
  mutate(NATIVITY = ifelse(NATIVITY == 1, 1, 0))

readr::write_csv(fx_pums_df, xzfile("/Users/avagutshall/desktop/folder/sdc.health_dev/Health Care Cost/Health Insurance/data/ffx_pums_hicov_full_2022.csv.xz", compression=9))
# fx_pums_df <- read_csv("../data/ffx_pums_hicov_full_2022.csv.xz") 

# tables ----------------------------------------------------------------------- 
hhls <- fx_pums_df %>% filter(SEX=='Female', age_group=='Adults (18-64)', race_eth=="Other") %>%
  group_by(HHL) %>%
  summarise(pop=sum(PWGTP), num_cov=sum(HICOV*PWGTP), pct_cov=(num_cov/pop)*100, 
            num_uncov=pop-num_cov, pct_uncov=100-pct_cov, 
            pct_frg_born=100-(sum(NATIVITY*PWGTP)/pop*100))

# household languages of uncovered women and girls
hhls2 <- fx_pums_df %>% filter(SEX=='Female', HICOV==1) %>%
  group_by(HHL) %>%
  summarise(count=sum(PWGTP))

# filter by sex, age
fx_girls <- fx_pums_df %>% filter(SEX=='Female', age_group=='Children \n(under 18)', race_eth != "Hispanic", race_eth != "Not Hispanic")

total_pop <- sum(fx_girls$PWGTP)
with_cov <- sum((fx_girls%>%filter(HICOV==1))$PWGTP)
without_cov <- sum((fx_girls%>%filter(HICOV==0))$PWGTP)

cat('\n\nEstimated Girls With Coverage:',
    with_cov, '\nEstimated Number of Girls Without Coverage:',
    without_cov, '\nEstimated Percent of Girls Without Coverage:',
    without_cov/total_pop*100)

# filter by sex, age
fx_wm <- fx_pums_df%>% filter(SEX=='Female', age_group=='Adults (18-64)', race_eth != "Hispanic", race_eth != "Not Hispanic")

total_pop <- sum(fx_wm$PWGTP)
with_cov <- sum((fx_wm%>%filter(HICOV==1))$PWGTP)
without_cov <- sum((fx_wm%>%filter(HICOV==0))$PWGTP)

cat('\n\nEstimated Women (19-64) With Coverage:',
    with_cov, '\nEstimated Number of Women 18-64 Without Coverage:',
    without_cov, '\nEstimated Percent of Women 18-64 Without Coverage:',
    without_cov/total_pop*100)

# filter by sex, age
fx_wm_65_plus <- fx_pums_df %>% filter(SEX=='Female', age_group=='Adults (65+)', race_eth != "Hispanic", race_eth != "Not Hispanic")

total_pop <- sum(fx_wm_65_plus$PWGTP)
with_cov <- sum((fx_wm_65_plus%>%filter(HICOV==1))$PWGTP)
without_cov <- sum((fx_wm_65_plus%>%filter(HICOV==0))$PWGTP)

cat('\n\nEstimated Women (65+) With Coverage:',
    with_cov, '\nEstimated Number of Women 65+ Without Coverage:',
    without_cov, '\nEstimated Percent of Women 65+ Without Coverage:',
    without_cov/total_pop*100)

#fx_pums_df %>% group_by(SEX, age_group, HICOV) %>% summarise(prop = survey_prop())

fx_by_race_sex <- fx_pums_df %>% mutate(HICOV=as.numeric(HICOV)) %>%
  group_by(PUMA, race_eth, SEX) %>% 
  summarise(total_pop=sum(PWGTP),
            num_cov=sum(HICOV*PWGTP),
            pct_cov=(sum(HICOV*PWGTP)/total_pop*100)) %>%
  mutate(geoid=paste0('51', PUMA), num_not_cov=total_pop-num_cov, pct_not_cov=(num_not_cov/total_pop)*100,
         pct_not_cov_rd = paste0(round(pct_not_cov, 0), '%'))

readr::write_csv(fx_by_race_sex, xzfile("/Users/avagutshall/Desktop/folder/sdc.health_dev/Health Care cost/Health Insurance/data/ffx_pums_hicov_grouped.csv.xz", compression=9))

 