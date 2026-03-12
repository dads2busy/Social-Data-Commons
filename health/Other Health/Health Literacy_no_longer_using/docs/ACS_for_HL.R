# ACS charateristics for Health Literacy
# packages
library(tidycensus)
library(tigris)
library(RPostgreSQL)
library(dplyr)
library(readr)

# installed census api key
readRenviron("~/.Renviron")
Sys.getenv("CENSUS_API_KEY")

# # acs vars search help
# vars_19 <- tidycensus::load_variables(year = 2019,
#                        dataset = "acs5",
#                        cache = TRUE)

acs_vars <- c(# tot pop
              "B02001_001",
              # white, black, native, asian, pi,
              "B02001_002", "B02001_003", "B02001_004", "B02001_005", "B02001_006",
              # other race, mixed
              "B02001_007", "B02001_008",
              # hispanic or latino
              "B01001I_001",
              # male
              "B01001_002",
              # female
              "B01001_026",
              # less 18 male
              "B01001_003", "B01001_004", "B01001_005", "B01001_006",
              # 18-24 male
              "B01001_007", "B01001_008", "B01001_009", "B01001_010",
              # 25-39 male
              "B01001_011", "B01001_012", "B01001_013",
              # 40-49 male
              "B01001_014", "B01001_015",
              # male 50-64
              "B01001_016", "B01001_017", "B01001_018", "B01001_019",
              # male 65-74
              "B01001_020", "B01001_021", "B01001_022",
              # male 74+
              "B01001_023", "B01001_024", "B01001_025",
              # female less 18
              "B01001_027", "B01001_028", "B01001_029", "B01001_030",
              # female 18-24
              "B01001_031", "B01001_032", "B01001_033", "B01001_034",
              # female 25-39
              "B01001_035", "B01001_036", "B01001_037",
              # female 40-49
              "B01001_038", "B01001_039",
              # female 50-64
              "B01001_040", "B01001_041", "B01001_042", "B01001_043",
              # female 65-74
              "B01001_044", "B01001_045", "B01001_046",
              # female 74+
              "B01001_047", "B01001_048", "B01001_049",
              # tot pop over 25 for educational attaiment
              "B15003_001",
              # no edu, less HS
              "B15003_002", "B15003_003", "B15003_004", "B15003_005", "B15003_006", "B15003_007",
              "B15003_008", "B15003_009", "B15003_010", "B15003_011", "B15003_012", "B15003_013",
              "B15003_014", "B15003_015", "B15003_016",
              # HS or GED
              "B15003_017", "B15003_018", "B15003_019", "B15003_020",
              # BS
              "B15003_022",
              # other/assoc degree
              "B15003_021", "B15003_024",
              # abv BS
              "B15003_023", "B15003_025",
              # pop 15 and older for marital status
              "B12001_001",
              # male never married
              "B12001_003",
              # male married
              "B12001_005",
              # male sep, div or wid
              "B12001_006", "B12001_009", "B12001_010",
              # female never married
              "B12001_012",
              # female married
              "B12001_014",
              # female sep div or wid
              "B12001_015", "B12001_018", "B12001_019",
              # income below PVL
              "B17001_002",
              # income above PVL
              "B17001_031",
              # born US
              "B05001_002", "B05001_003",
              # not born US
              "B05001_004", "B05001_005", "B05001_006",
              # pop over 5
              "B16001_001",
              # speak Eng at home
              "B16001_002",
              # oth lang
              "B16001_003", "B16001_006", "B16001_009", "B16001_012", "B16001_015", "B16001_018",
              "B16001_021", "B16001_024", 'B16001_027', "B16001_030", "B16001_033", "B16001_036",
              "B16001_039", "B16001_042", "B16001_045", "B16001_048", "B16001_051", "B16001_054",
              "B16001_057", "B16001_060", "B16001_063", "B16001_066", "B16001_069", "B16001_072",
              "B16001_075", "B16001_078", "B16001_081", "B16001_084", "B16001_087", "B16001_090",
              "B16001_093", "B16001_096", "B16001_099", "B16001_102", "B16001_105", "B16001_108",
              "B16001_111", "B16001_114", "B16001_117", "B16001_120", "B16001_123", "B16001_126")

acs_init <- get_acs(geography="tract",
                      state="VA",
                      variables=acs_vars,
                      year=2019,
                      cache_table=TRUE,
                      output="wide")

acs_estimates <- acs_init %>% transmute(
  GEOID=GEOID,
  NAME = NAME,
  #age
  age_less_18  =  (B01001_003E+B01001_004E+B01001_005E+B01001_006E +
                     B01001_027E + B01001_028E + B01001_029E + B01001_030E) /B02001_001E,
  age_18_24 = (B01001_007E + B01001_008E + B01001_009E + B01001_007E +
                 B01001_031E + B01001_032E + B01001_033E + B01001_034E)/B02001_001E,
  age_25_39 = (B01001_011E+ B01001_012E+ B01001_013E +
                 B01001_035E + B01001_036E + B01001_037E)/B02001_001E,
  age_40_49 = (B01001_014E + B01001_015E +
                 B01001_038E + B01001_039E)/B02001_001E,
  age_50_64 = (B01001_016E + B01001_017E + B01001_018E + B01001_019E +
                 B01001_040E + B01001_041E + B01001_042E + B01001_043E)/B02001_001E,
  age_65_74 = (B01001_020E + B01001_021E + B01001_022E +
                 B01001_044E + B01001_045E + B01001_046E)/B02001_001E,
  #male = B01001_002E/B02001_001E,
  female = B01001_026E/B02001_001E,
  #white = B02001_002E/B02001_001E,
  hispanic = B01001I_001E/B02001_001E,
  black = B02001_003E/B02001_001E,
  asian_pi = (B02001_005E+B02001_006E)/B02001_001E,
  native = B02001_004E/B02001_001E,
  mixed = (B02001_007E+B02001_008E)/B02001_001E,
  HS_GED = (B15003_017E + B15003_018E + B15003_019E + B15003_020E)/B15003_001E,
  no_edu = (B15003_002E + B15003_003E + B15003_004E + B15003_005E + B15003_006E + B15003_007E +
              B15003_008E + B15003_009E + B15003_010E + B15003_011E + B15003_012E + B15003_013E +
              B15003_014E + B15003_015E + B15003_016E)/B02001_001E,
  BS_degree = B15003_022E/B15003_001E,
  above_BS = (B15003_023E + B15003_025E)/B15003_001E,
  oth_degree = (B15003_021E + B15003_024E)/B15003_001E,
  below_PVL = (B17001_002E)/B02001_001E,
  wid_sep_div = (B12001_006E + B12001_009E + B12001_010E + B12001_015E +
                   B12001_018E + B12001_019E)/B12001_001E,
  nev_married = (B12001_003E + B12001_012E)/B12001_001E,
  lang_eng = B16001_002E/B16001_001E,
  lang_oth = (B16001_003E + B16001_006E + B16001_009E + B16001_012E + B16001_015E + B16001_018E +
                B16001_021E + B16001_024E + B16001_027E + B16001_030E + B16001_033E +
                B16001_036E + B16001_039E + B16001_042E + B16001_045E + B16001_048E +
                B16001_051E + B16001_054E + B16001_057E + B16001_060E + B16001_063E +
                B16001_066E  + B16001_069E + B16001_072E + B16001_075E + B16001_078E +
                B16001_081E + B16001_084E + B16001_087E + B16001_090E + B16001_093E +
                B16001_096E + B16001_099E + B16001_102E + B16001_105E + B16001_108E +
                B16001_111E + B16001_114E + B16001_117E + B16001_120E +
                B16001_123E + B16001_126E)/B16001_001E,
  born_us = (B05001_002E + B05001_003E)/B02001_001E,
  born_not_us = (B05001_004E + B05001_005E + B05001_006E)/B02001_001E)

X_pred_tr = acs_estimates %>% select(-NAME)
write_csv(X_pred_tr, "~/R/access_to_edu/HL_X_pred_tr.csv")

acs_init_ct <- get_acs(geography="county",
                    state="VA",
                    variables=acs_vars,
                    year=2019,
                    cache_table=TRUE,
                    output="wide")

acs_est_ct <- acs_init_ct %>% transmute(
  GEOID=GEOID,
  #age
  age_less_18  =  (B01001_003E+B01001_004E+B01001_005E+B01001_006E +
                     B01001_027E + B01001_028E + B01001_029E + B01001_030E) /B02001_001E,
  age_18_24 = (B01001_007E + B01001_008E + B01001_009E + B01001_007E +
                 B01001_031E + B01001_032E + B01001_033E + B01001_034E)/B02001_001E,
  age_25_39 = (B01001_011E+ B01001_012E+ B01001_013E +
                 B01001_035E + B01001_036E + B01001_037E)/B02001_001E,
  age_40_49 = (B01001_014E + B01001_015E +
                 B01001_038E + B01001_039E)/B02001_001E,
  age_50_64 = (B01001_016E + B01001_017E + B01001_018E + B01001_019E +
                 B01001_040E + B01001_041E + B01001_042E + B01001_043E)/B02001_001E,
  age_65_74 = (B01001_020E + B01001_021E + B01001_022E +
                 B01001_044E + B01001_045E + B01001_046E)/B02001_001E,
  #male = B01001_002E/B02001_001E,
  female = B01001_026E/B02001_001E,
  #white = B02001_002E/B02001_001E,
  hispanic = B01001I_001E/B02001_001E,
  black = B02001_003E/B02001_001E,
  asian_pi = (B02001_005E+B02001_006E)/B02001_001E,
  native = B02001_004E/B02001_001E,
  mixed = (B02001_007E+B02001_008E)/B02001_001E,
  HS_GED = (B15003_017E + B15003_018E + B15003_019E + B15003_020E)/B15003_001E,
  no_edu = (B15003_002E + B15003_003E + B15003_004E + B15003_005E + B15003_006E + B15003_007E +
              B15003_008E + B15003_009E + B15003_010E + B15003_011E + B15003_012E + B15003_013E +
              B15003_014E + B15003_015E + B15003_016E)/B02001_001E,
  BS_degree = B15003_022E/B15003_001E,
  above_BS = (B15003_023E + B15003_025E)/B15003_001E,
  oth_degree = (B15003_021E + B15003_024E)/B15003_001E,
  below_PVL = (B17001_002E)/B02001_001E,
  wid_sep_div = (B12001_006E + B12001_009E + B12001_010E + B12001_015E +
                   B12001_018E + B12001_019E)/B12001_001E,
  nev_married = (B12001_003E + B12001_012E)/B12001_001E,
  lang_eng = B16001_002E/B16001_001E,
  lang_oth = (B16001_003E + B16001_006E + B16001_009E + B16001_012E + B16001_015E + B16001_018E +
                B16001_021E + B16001_024E + B16001_027E + B16001_030E + B16001_033E +
                B16001_036E + B16001_039E + B16001_042E + B16001_045E + B16001_048E +
                B16001_051E + B16001_054E + B16001_057E + B16001_060E + B16001_063E +
                B16001_066E  + B16001_069E + B16001_072E + B16001_075E + B16001_078E +
                B16001_081E + B16001_084E + B16001_087E + B16001_090E + B16001_093E +
                B16001_096E + B16001_099E + B16001_102E + B16001_105E + B16001_108E +
                B16001_111E + B16001_114E + B16001_117E + B16001_120E +
                B16001_123E + B16001_126E)/B16001_001E,
  born_us = (B05001_002E + B05001_003E)/B02001_001E,
  born_not_us = (B05001_004E + B05001_005E + B05001_006E)/B02001_001E)

write_csv(acs_est_ct, "~/R/access_to_edu/HL_X_pred_ct.csv")

# HEALTH DISTRICTS
# load health dist data
# connect to database
con <- dbConnect(PostgreSQL(),
                 dbname = "sdad",
                 host = "postgis1",
                 port = 5432,
                 user = "hc2cc",
                 password = "hc2cchc2cc")
geo_names <- dbGetQuery(con, "SELECT * FROM dc_geographies.ncr_cttrbg_tiger_2010_2020_geo_names")

health_dist <- dbGetQuery(con, "SELECT * FROM dc_common.va_hdct_sdad_2021_health_district_counties")

dbDisconnect(con)

counties <- geo_names %>% filter(region_type=="county")
tracts <- geo_names %>% filter(region_type == "tract")


acs_counts_ct <- acs_init_ct %>% transmute(
  GEOID=GEOID,
  tot_pop = B02001_001E,
  pop_over_25 = B15003_001E,
  pop_over_15 = B12001_001E,
  pop_over_5 = B16001_001E,
  #age
  age_less_18  =  (B01001_003E+B01001_004E+B01001_005E+B01001_006E +
                     B01001_027E + B01001_028E + B01001_029E + B01001_030E),
  age_18_24 = (B01001_007E + B01001_008E + B01001_009E + B01001_007E +
                 B01001_031E + B01001_032E + B01001_033E + B01001_034E),
  age_25_39 = (B01001_011E+ B01001_012E+ B01001_013E +
                 B01001_035E + B01001_036E + B01001_037E),
  age_40_49 = (B01001_014E + B01001_015E +
                 B01001_038E + B01001_039E),
  age_50_64 = (B01001_016E + B01001_017E + B01001_018E + B01001_019E +
                 B01001_040E + B01001_041E + B01001_042E + B01001_043E),
  age_65_74 = (B01001_020E + B01001_021E + B01001_022E +
                 B01001_044E + B01001_045E + B01001_046E),
  #male = B01001_002E/B02001_001E,
  female = B01001_026E,
  #white = B02001_002E/B02001_001E,
  hispanic = B01001I_001E,
  black = B02001_003E,
  asian_pi = (B02001_005E+B02001_006E),
  native = B02001_004E,
  mixed = (B02001_007E+B02001_008E),
  HS_GED = (B15003_017E + B15003_018E + B15003_019E + B15003_020E),
  no_edu = (B15003_002E + B15003_003E + B15003_004E + B15003_005E + B15003_006E + B15003_007E +
              B15003_008E + B15003_009E + B15003_010E + B15003_011E + B15003_012E + B15003_013E +
              B15003_014E + B15003_015E + B15003_016E),
  BS_degree = B15003_022E,
  above_BS = (B15003_023E + B15003_025E),
  oth_degree = (B15003_021E + B15003_024E),
  below_PVL = (B17001_002E),
  wid_sep_div = (B12001_006E + B12001_009E + B12001_010E + B12001_015E +
                   B12001_018E + B12001_019E),
  nev_married = (B12001_003E + B12001_012E),
  lang_eng = B16001_002E,
  lang_oth = (B16001_003E + B16001_006E + B16001_009E + B16001_012E + B16001_015E + B16001_018E +
                B16001_021E + B16001_024E + B16001_027E + B16001_030E + B16001_033E +
                B16001_036E + B16001_039E + B16001_042E + B16001_045E + B16001_048E +
                B16001_051E + B16001_054E + B16001_057E + B16001_060E + B16001_063E +
                B16001_066E  + B16001_069E + B16001_072E + B16001_075E + B16001_078E +
                B16001_081E + B16001_084E + B16001_087E + B16001_090E + B16001_093E +
                B16001_096E + B16001_099E + B16001_102E + B16001_105E + B16001_108E +
                B16001_111E + B16001_114E + B16001_117E + B16001_120E +
                B16001_123E + B16001_126E),
  born_us = (B05001_002E + B05001_003E),
  born_not_us = (B05001_004E + B05001_005E + B05001_006E)
  )


acs_est_hd <- left_join(acs_counts_ct, health_dist[, c("geoid_county", "geoid")],
                        by = c("GEOID" = "geoid_county"))


acs_est_hd <- acs_est_hd  %>% select(-(GEOID))

acs_est_hd <- acs_est_hd  %>%
  group_by(geoid) %>%
  summarise_all(sum) %>%
  ungroup()

acs_est_hd <- acs_est_hd  %>% transmute(
  GEOID = geoid,
  age_less_18 = age_less_18/tot_pop,
  age_18_24 = age_18_24/tot_pop,
  age_25_39 = age_25_39/tot_pop,
  age_40_49 = age_40_49/tot_pop,
  age_50_64 = age_50_64/tot_pop,
  age_65_74 = age_65_74/tot_pop,
  female = female/tot_pop,
  black = black/tot_pop,
  hispanic = hispanic/tot_pop,
  asian_pi = asian_pi/tot_pop,
  native = native/tot_pop,
  mixed = mixed/tot_pop,
  HS_GED = HS_GED/pop_over_25,
  no_edu = no_edu/pop_over_25,
  BS_degree = BS_degree/pop_over_25,
  above_BS = above_BS/pop_over_25,
  oth_degree = oth_degree/pop_over_25,
  below_PVL = below_PVL/tot_pop,
  wid_sep_div = wid_sep_div/pop_over_15,
  nev_married = nev_married/pop_over_15,
  lang_eng = lang_eng/pop_over_5,
  lang_oth = lang_oth/pop_over_5,
  born_us = born_us/tot_pop,
  born_not_us = born_not_us/tot_pop
)

write_csv(acs_est_hd, "~/R/access_to_edu/HL_X_pred_hd.csv")

############################################################
# read in health literacy estimates
hl_est_tr <- read_csv("~/R/access_to_edu/hl_est_tr.csv")
hl_est_tr$GEOID <- as.character(hl_est_tr$GEOID)
hl_est_ct <- read_csv("~/R/access_to_edu/hl_est_ct.csv")
hl_est_ct$GEOID <- as.character(hl_est_ct$GEOID)
hl_est_hd <- read_csv("~/R/access_to_edu/hl_est_hd.csv")

# add region names
hl_est_tr <- left_join(hl_est_tr, tracts[, c("region_name", "geoid")],
                        by = c("GEOID" = "geoid"))
hl_est_ct <- left_join(hl_est_ct, counties[, c("region_name", "geoid")],
                       by = c("GEOID" = "geoid"))
health_dist$geoid <- as.numeric(health_dist$geoid)
# merge to literacy estimates
hl_est_hd <- merge(hl_est_hd, health_dist[, c("region_name", "geoid")],
                      by.x="GEOID",
                      by.y="geoid",
                      all.x = TRUE, all.y = FALSE)
hl_est_hd <- hl_est_hd %>% distinct()

hl_est_tr["region_type"] <- "tract"
hl_est_tr["year"] <- 2019
hl_est_tr["measure"] <- "health_literacy_estimate"
hl_est_tr["measure_type"] <- "index"
# rename columns
names(hl_est_tr)[1] <- 'value'
names(hl_est_tr)[2] <- 'geoid'

hl_est_tr <- hl_est_tr[, c(2, 4, 3, 5, 6,1,7)]

hl_est_ct["region_type"] <- "county"
hl_est_ct["year"] <- 2019
hl_est_ct["measure"] <- "health_literacy_estimate"
hl_est_ct["measure_type"] <- "index"
# rename columns
names(hl_est_ct)[1] <- 'value'
names(hl_est_ct)[2] <- 'geoid'

hl_est_ct <- hl_est_ct[, c(2, 4, 3, 5, 6,1,7)]

hl_est_hd["region_type"] <- "health_district"
hl_est_hd["year"] <- 2019
hl_est_hd["measure"] <- "health_literacy_estimate"
hl_est_hd["measure_type"] <- "index"
# rename columns
names(hl_est_hd)[2] <- 'value'
names(hl_est_hd)[1] <- 'geoid'
hl_est_hd <- hl_est_hd[, c(1, 4, 3, 5, 6,2,7)]

# upload to db
# connect to database
con <- dbConnect(PostgreSQL(),
                 dbname = "sdad",
                 host = "postgis1",
                 port = 5432,
                 user = "hc2cc",
                 password = "hc2cchc2cc")

dbWriteTable(con, c("dc_education_training", "va_tr_sdad_2019_health_literacy_estimates"), hl_est_tr,
             row.names = F)
dbWriteTable(con, c("dc_education_training", "va_ct_sdad_2019_health_literacy_estimates"), hl_est_ct,
             row.names = F)
dbWriteTable(con, c("dc_education_training", "va_hd_sdad_2019_health_literacy_estimates"), hl_est_hd,
             row.names = F)


# remove old tables
dbRemoveTable(con, c("dc_education_training", "va_hd_sdad_2019_health_literacy_estimates"))
dbRemoveTable(con, c("dc_education_training", "va_ct_sdad_2019_health_literacy_estimates"))

# change ownership
dbSendStatement(con, "ALTER TABLE dc_education_training.va_hd_sdad_2019_health_literacy_estimates
                    OWNER TO data_commons")
dbSendStatement(con, "ALTER TABLE dc_education_training.va_ct_sdad_2019_health_literacy_estimates
                    OWNER TO data_commons")

dbDisconnect(con)

# pull data from DB
con <- dbConnect(PostgreSQL(),
                 dbname = "sdad",
                 host = "postgis1",
                 port = 5432,
                 user = "hc2cc",
                 password = "hc2cchc2cc")
geo_names <- dbGetQuery(con, "SELECT * FROM dc_geographies.ncr_cttrbg_tiger_2010_2020_geo_names")
health_dist <- dbGetQuery(con, "SELECT * FROM dc_geographies.va_hd_vdh_2021_health_district_geo_names")
hl_est_hd <- dbGetQuery(con, "SELECT * FROM dc_education_training.va_hd_sdad_2019_health_literacy_estimates")
hl_est_ct <- dbGetQuery(con, "SELECT * FROM dc_education_training.va_ct_sdad_2019_health_literacy_estimates")

dbDisconnect(con)

counties <- geo_names %>% filter(region_type=="county")
# delete old county names and hd ids
hl_est_ct <-  hl_est_ct %>% select(-c("row.names", "region_name", "region_type"))
hl_est_hd <-  hl_est_hd %>% select(-c("row.names", "geoid", "region_type"))

# add new names and geoids
hl_est_ct <- left_join(hl_est_ct, counties, by="geoid")
hl_est_hd <- left_join(hl_est_hd, health_dist, by="region_name")

#re-arrange cols
hl_est_ct <- hl_est_ct[, c(1, 7,6, 2, 3, 4, 5)]
hl_est_hd <- hl_est_hd[, c(6, 7, 1, 2, 3, 4, 5)]



# # get census block geography
# tract_geo <- tigris::tracts(state='VA', cb=TRUE, class = "sf")
#
# # merge to literacy estimates
# literacy_tr <- merge(hl_est_tr, tract_geo,
#                       by.x="GEOID",
#                       by.y="GEOID",
#                       all.x = TRUE, all.y = FALSE)
# # maps
# ggplot() +
#   geom_sf(data = literacy_tr, size = 0.2, aes(fill = `0`, geometry = geometry)) +
#   scale_fill_gradient(name="Health Literacy Estimate",
#                       low = "red", high = "green") +
#   xlab("longitude") + ylab("latitude") +
#   labs(title="Health Literacy Estimate",
#        subtitle = "using MEPS 2019 at the Census tract level")
#
