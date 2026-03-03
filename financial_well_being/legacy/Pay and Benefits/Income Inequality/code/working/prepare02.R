library(tidycensus)
library(tidyr)
library(dplyr)

View(pums_variables)
# https://www2.census.gov/programs-surveys/acs/tech_docs/pums/data_dict/PUMSDataDict13.txt

# "WAGP": Wage and salary income
# "ADJINC" : Income adjustment
# "HISP"
# "RAC1P"
# "AGEP"
# "SEX"
# "NATIVITY"
# "HHL"
# "ESR": Employment status recode
# WKHP: Hours worked per week

# QUESTIONS:  What do we think about sample sizes? Should we be making aggregations?
#             What do we think about comparison groups?

acs_pums <- get_pums(
  variables =
    c("WAGP","ADJINC","HISP","RAC1P","AGEP","SEX","NATIVITY","HHL", "ESR", "WKHP"),
  state = "51",
  puma = c("59301","59302","59303","59304","59305","59306","59307","59308","59309"),
  survey = "acs5",
  year = 2021)

# OVERALL WAGE GAP (BY HOURS AND AGE SPLITS) ----------------------------------------

mean_wages <- acs_pums %>%
  filter(ESR != c("6"), ESR != "b") %>%
  mutate(hours = ifelse(WKHP > 20, "full-time", "part-time"),
         age = case_when(
           AGEP >= 16 & AGEP <= 29 ~ "16 to 29",
           AGEP > 29 & AGEP <= 49 ~ "30 to 49",
           AGEP > 49 ~ "over 50",
         )) %>%
  mutate(sex = ifelse(SEX == 1, "male", "female")) %>%
  group_by(PUMA, sex, hours, age) %>%
  summarise(mean_wage = mean(WAGP), sample = n())

male_wages <- mean_wages %>% filter(sex == "male") %>% rename(male_mean_wage = mean_wage) %>% ungroup() %>% select(-sample, -sex)

wage_gap <-mean_wages %>% ungroup() %>%
  left_join(male_wages, by = c("PUMA", "hours", "age")) %>%
  mutate(wage_gap = mean_wage/male_mean_wage)

#%>%
#  group_by(PUMA, hours, age) %>% mutate(male_wage =  #%>%
#  pivot_wider(id_cols = "PUMA", names_from = "SEX", values_from = "AVG_WAGE") %>%
#  mutate(WAGE_GAP = `2`/`1`)

# HISPANIC WAGE GAP (BY HOURS AND AGE SPLITS) ----------------------------------------

mean_wages <- acs_pums %>%
  filter(ESR != c("6"), ESR != "b") %>%
  mutate(hours = ifelse(WKHP > 20, "full-time", "part-time"),
         age = case_when(
           AGEP >= 16 & AGEP <= 29 ~ "16 to 29",
           AGEP > 29 & AGEP <= 49 ~ "30 to 49",
           AGEP > 49 ~ "over 50",
         ),
         hispanic = ifelse(HISP == "01", "white", "hispanic")) %>%
  mutate(sex = ifelse(SEX == 1, "male", "female")) %>%
  group_by(PUMA, sex, hours, age, hispanic) %>%
  summarise(mean_wage = mean(WAGP), sample = n())

male_wages <- mean_wages %>% filter(sex == "male") %>% rename(male_mean_wage = mean_wage) %>% ungroup() %>% select(-sample, -sex)

wage_gap <-mean_wages %>% ungroup() %>%
  left_join(male_wages, by = c("PUMA", "hours", "age", "hispanic")) %>%
  mutate(wage_gap = mean_wage/male_mean_wage)

# RACE WAGE GAP (BY HOURS AND AGE SPLITS) ----------------------------------------

mean_wages <- acs_pums %>%
  filter(ESR != c("6"), ESR != "b") %>%
  mutate(hours = ifelse(WKHP > 20, "full-time", "part-time"),
         age = case_when(
           AGEP >= 16 & AGEP <= 29 ~ "16 to 29",
           AGEP > 29 & AGEP <= 49 ~ "30 to 49",
           AGEP > 49 ~ "over 50",
         ),
         race = case_when(
           RAC1P == 1 ~ "white_alone",
           RAC1P == 2 ~ "black_alone",
           RAC1P == 3 ~ "native_alone",
           RAC1P == 4 ~ "alaska_alone",
           RAC1P == 5 ~ "other_native_alone",
           RAC1P == 6 ~ "asian_alone",
           RAC1P == 7 ~ "native_hawaii_alone",
           RAC1P == 8 ~ "other",
           RAC1P == 9 ~ "two_or_more")) %>%
  mutate(sex = ifelse(SEX == 1, "male", "female")) %>%
  group_by(PUMA, sex, hours, age, race) %>%
  summarise(mean_wage = mean(WAGP), sample = n())

# RACE + LANGUAGE WAGE GAP ----------------------------

mean_wages <- acs_pums %>%
  filter(ESR != c("6"), ESR != "b") %>%
  mutate(hours = ifelse(WKHP > 20, "full-time", "part-time"),
         age = case_when(
           AGEP >= 16 & AGEP <= 29 ~ "16 to 29",
           AGEP > 29 & AGEP <= 49 ~ "30 to 49",
           AGEP > 49 ~ "over 50",
         ),
         race = case_when(
           RAC1P == 1 ~ "white_alone",
           RAC1P == 2 ~ "black_alone",
           RAC1P == 3 ~ "native_alone",
           RAC1P == 4 ~ "alaska_alone",
           RAC1P == 5 ~ "other_native_alone",
           RAC1P == 6 ~ "asian_alone",
           RAC1P == 7 ~ "native_hawaii_alone",
           RAC1P == 8 ~ "other",
           RAC1P == 9 ~ "two_or_more"),
         language = ifelse(HHL == 1, "english", "non-english")) %>%
         #language = case_when(
        #   HHL == "b" ~ "n/a",
        #   HHL == 1 ~ "english",
        #   HHL == 2 ~ "spanish",
        #   HHL == 3 ~ "other_indo_european",
        #   HHL == 4 ~ "asian",
        #   HHL == 5 ~ "other")) %>%
  mutate(sex = ifelse(SEX == 1, "male", "female")) %>%
  group_by(PUMA, sex, hours, age, race, language) %>%
  summarise(mean_wage = mean(WAGP), sample = n())

male_wages <- mean_wages %>% filter(sex == "male") %>% rename(male_mean_wage = mean_wage) %>% ungroup() %>% select(-sample, -sex)

wage_gap <-mean_wages %>% ungroup() %>%
  left_join(male_wages, by = c("PUMA", "hours", "age", "race", "language")) %>%
  mutate(wage_gap = mean_wage/male_mean_wage)

# RACE + NATIVITY WAGE GAP ----------------------------

mean_wages <- acs_pums %>%
  filter(ESR != c("6"), ESR != "b") %>%
  mutate(hours = ifelse(WKHP > 20, "full-time", "part-time"),
         age = case_when(
           AGEP >= 16 & AGEP <= 29 ~ "16 to 29",
           AGEP > 29 & AGEP <= 49 ~ "30 to 49",
           AGEP > 49 ~ "over 50",
         ),
         race = case_when(
           RAC1P == 1 ~ "white_alone",
           RAC1P == 2 ~ "black_alone",
           RAC1P == 3 ~ "native_alone",
           RAC1P == 4 ~ "alaska_alone",
           RAC1P == 5 ~ "other_native_alone",
           RAC1P == 6 ~ "asian_alone",
           RAC1P == 7 ~ "native_hawaii_alone",
           RAC1P == 8 ~ "other",
           RAC1P == 9 ~ "two_or_more")) %>%
  mutate(nativity = ifelse(NATIVITY == 1, "native", "foreign born")) %>%
  mutate(sex = ifelse(SEX == 1, "male", "female")) %>%
  group_by(PUMA, sex, hours, age, race, nativity) %>%
  summarise(mean_wage = mean(WAGP), sample = n())

male_wages <- mean_wages %>% filter(sex == "male") %>% rename(male_mean_wage = mean_wage) %>% ungroup() %>% select(-sample, -sex)

wage_gap <-mean_wages %>% ungroup() %>%
  left_join(male_wages, by = c("PUMA", "hours", "age", "race", "nativity")) %>%
  mutate(wage_gap = mean_wage/male_mean_wage)




acs_pums %>%
  filter(ESR != c("6"), ESR != "b") %>%
  mutate(HISP = ifelse(HISP == "01", "white", "hispanic")) %>%
  group_by(PUMA, SEX, HISP) %>% summarise(AVG_WAGE = mean(WAGP)) %>%
  pivot_wider(id_cols = "PUMA", names_from = c("SEX", "HISP"), values_from = "AVG_WAGE") #%>%
  mutate(WAGE_GAP = `2`/`1`)

test <- acs_pums %>%
  filter(ESR != c("6"), ESR != "b") %>%
  mutate(race = case_when(
    RAC1P == 1 ~ "white_alone",
    RAC1P == 2 ~ "black_alone",
    RAC1P == 3 ~ "native_alone",
    RAC1P == 4 ~ "alaska_alone",
    RAC1P == 5 ~ "other_native_alone",
    RAC1P == 6 ~ "asian_alone",
    RAC1P == 7 ~ "native_hawaii_alone",
    RAC1P == 8 ~ "other",
    RAC1P == 9 ~ "two_or_more")) %>%
  group_by(PUMA, SEX, race) %>% summarise(AVG_WAGE = mean(WAGP)) %>%
  pivot_wider(id_cols = "PUMA", names_from = c("SEX", "RAC1P"), values_from = "AVG_WAGE") #%>%
  mutate(WAGE_GAP = `2`/`1`)

test <- acs_pums %>%
    filter(ESR != c("6"), ESR != "b") %>%
    mutate(RAC1P = case_when(
      RAC1P == 1 ~ "white_alone",
      RAC1P == 2 ~ "black_alone",
      RAC1P == 3 ~ "native_alone",
      RAC1P == 4 ~ "alaska_alone",
      RAC1P == 5 ~ "other_native_alone",
      RAC1P == 6 ~ "asian_alone",
      RAC1P == 7 ~ "native_hawaii_alone",
      RAC1P == 8 ~ "other",
      RAC1P == 9 ~ "two_or_more")) %>%
    group_by(PUMA, SEX, RAC1P, NATIVITY) %>% summarise(AVG_WAGE = mean(WAGP)) %>%
    pivot_wider(id_cols = "PUMA", names_from = c("SEX", "RAC1P", "NATIVITY"), values_from = "AVG_WAGE") #%>%
  mutate(WAGE_GAP = `2`/`1`)

test <- acs_pums %>%
    filter(ESR != c("6"), ESR != "b") %>%
    mutate(RAC1P = case_when(
      RAC1P == 1 ~ "white_alone",
      RAC1P == 2 ~ "black_alone",
      RAC1P == 3 ~ "native_alone",
      RAC1P == 4 ~ "alaska_alone",
      RAC1P == 5 ~ "other_native_alone",
      RAC1P == 6 ~ "asian_alone",
      RAC1P == 7 ~ "native_hawaii_alone",
      RAC1P == 8 ~ "other",
      RAC1P == 9 ~ "two_or_more")) %>%
    mutate(HHL = case_when(
      HHL == "b" ~ "n/a",
      HHL == 1 ~ "english",
      HHL == 2 ~ "spanish",
      HHL == 3 ~ "other_indo_european",
      HHL == 4 ~ "asian",
      HHL == 5 ~ "other")) %>%
    group_by(PUMA, SEX, RAC1P, HHL) %>% summarise(AVG_WAGE = mean(WAGP)) %>%
    pivot_wider(id_cols = "PUMA", names_from = c("SEX", "RAC1P", "HHL"), values_from = "AVG_WAGE") #%>%
  mutate(WAGE_GAP = `2`/`1`)
