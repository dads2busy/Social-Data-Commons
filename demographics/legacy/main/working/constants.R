# likely constants to store:
#  - years
#  - geographies
#  - geography for direct method

# data range variables
ACS_GEOS <- c('tract','county','block group')
STATES <- c('VA','MD','DC')
YEARS <- 2016:2021

# acs var dict for each topic
VARS <- list("Age" = c(total_pop = "B01001_001",
    male_under_5 = "B01001_003", male_5_9 = "B01001_004",
    male_10_14 = "B01001_005", male_15_17 = "B01001_006",
    male_18_19 = "B01001_007", male_20 = "B01001_008",
    male_21 = "B01001_009", male_22_24 = "B01001_010",
    male_25_29 = "B01001_011", male_30_34 = "B01001_012",
    male_35_39 = "B01001_013", male_40_44 = "B01001_014",
    male_45_49 = "B01001_015", male_50_54 = "B01001_016",
    male_55_59 = "B01001_017", male_60_61 = "B01001_018",
    male_62_64 = "B01001_019", male_65_66 = "B01001_020",
    male_67_69 = "B01001_021", male_70_74 = "B01001_022",
    male_75_79 = "B01001_023", male_80_84 = "B01001_024",
    male_over_85 = "B01001_025",
    female_under_5 = "B01001_027", female_5_9 = "B01001_028",
    female_10_14 = "B01001_029", female_15_17 = "B01001_030",
    female_18_19 = "B01001_031", female_20 = "B01001_032",
    female_21 = "B01001_033", female_22_24 = "B01001_034",
    female_25_29 = "B01001_035", female_30_34 = "B01001_036",
    female_35_39 = "B01001_037", female_40_44 = "B01001_038",
    female_45_49 = "B01001_039", female_50_54 = "B01001_040",
    female_55_59 = "B01001_041", female_60_61 = "B01001_042",
    female_62_64 = "B01001_043", female_65_66 = "B01001_044",
    female_67_69 = "B01001_045", female_70_74 = "B01001_046",
    female_75_79 = "B01001_047", female_80_84 = "B01001_048",
    female_over_85 = "B01001_049"),
  "Gender" = c(total_pop = "B01001_001",
    male = "B01001_002",
    female = "B01001_026"),
  "Language" = c(total_hh = "C16002_001",
    limited_english_spanish = "C16002_004",
    limited_english_indo_europe = "C16002_007",
    limited_english_asian_pacific = "C16002_010",
    limited_english_other_language = "C16002_013"),
  "Race" = c(total_race = "B02001_001",
    wht_alone = "B02001_002",
    afr_amer_alone = "B02001_003",
    native_alone = "B02001_004",
    asian_alone = "B02001_005",
    pacific_islander_alone = "B02001_006",
    other_language = "B02001_007",
    two_or_more = "B02001_008",
    pop_eth_tot = "B03003_001", 
    pop_hispanic_or_latino = "B03003_003"),
  "Veteran" = c(vet_denom = "B21001_001", 
    num_vet = "B21001_002"))

