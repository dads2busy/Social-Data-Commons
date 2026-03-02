# Libraries --------------------------------------------------------------------
library(dplyr)
library(sf)
# library(httr)
library(rjson)
library(tidyr)
library(readr)
library(tidycensus)
library(geojsonio)
census_api_key(Sys.getenv('census_api_key'))

duplicate <- function(df, methods) {
  duplicated <- NULL
  
  for (method in methods) {
    temp <- df %>% mutate(measure=paste0(measure, '_', method))
    duplicated <- rbind(duplicated, temp)
  }
  
  return(duplicated)
}

get_ncr <- function(df) {
  # get the list of tracts, counties and block groups from NCR
  temp_bg2010 <- read_sf('https://raw.githubusercontent.com/uva-bi-sdad/sdc.geographies/main/NCR/Census%20Geographies/Block%20Group/2010/data/distribution/ncr_geo_census_cb_2010_census_block_groups.geojson') %>%
    select(geoid,region_type,year) %>% st_drop_geometry()
  temp_bg2020 <- read_sf('https://raw.githubusercontent.com/uva-bi-sdad/sdc.geographies/main/NCR/Census%20Geographies/Block%20Group/2020/data/distribution/ncr_geo_census_cb_2020_census_block_groups.geojson') %>%
    select(geoid,region_type,year) %>% st_drop_geometry()
  temp_ct2010 <- read_sf('https://raw.githubusercontent.com/uva-bi-sdad/sdc.geographies/main/NCR/Census%20Geographies/County/2010/data/distribution/ncr_geo_census_cb_2010_counties.geojson') %>%
    select(geoid,region_type,year) %>% st_drop_geometry()
  temp_ct2020 <- read_sf('https://raw.githubusercontent.com/uva-bi-sdad/sdc.geographies/main/NCR/Census%20Geographies/County/2020/data/distribution/ncr_geo_census_cb_2020_counties.geojson') %>%
    select(geoid,region_type,year) %>% st_drop_geometry()
  temp_tr2010 <- read_sf('https://raw.githubusercontent.com/uva-bi-sdad/sdc.geographies/main/NCR/Census%20Geographies/Tract/2010/data/distribution/ncr_geo_census_cb_2010_census_tracts.geojson') %>%
    select(geoid,region_type,year) %>% st_drop_geometry()
  temp_tr2020 <- read_sf('https://raw.githubusercontent.com/uva-bi-sdad/sdc.geographies/main/NCR/Census%20Geographies/Tract/2020/data/distribution/ncr_geo_census_cb_2020_census_tracts.geojson') %>%
    select(geoid,region_type,year) %>% st_drop_geometry()
  
  ncr_geo <- rbind(temp_bg2010,temp_bg2020,temp_ct2010,temp_ct2020,temp_tr2010,temp_tr2020) %>%
    rename(census_year=year) %>%
    mutate(geoid=format(geoid, scientific = FALSE, justify='none'))
  
  ncr <- merge(df, ncr_geo, by.x=c('geoid','region_type','census_year'), by.y=c('geoid','region_type','census_year'), all.y=T) %>%
    select(geoid,region_name,region_type,year,measure,value,moe)
  
  return(ncr)
}

get_state <- function(df, state_col, state) {
  #' subsets a dataframe for a specific state
  #' param
  
  return(df %>% filter(state_col==state))
}

# TODO: revisit
calc_distribution <- function(topic, df) {
  if (topic=="Age") {
    return (df %>%
      mutate(age_total_count = total_popE,
             age_under_20_count = male_under_5E + male_5_9E + male_10_14E + male_15_17E + male_18_19E + 
               female_under_5E + female_5_9E + female_10_14E + female_15_17E + female_18_19E,
             age_20_64_count = male_20E + male_21E + male_22_24E + male_25_29E + male_30_34E + male_35_39E +
               male_40_44E +  male_45_49E + male_50_54E + male_55_59E + male_60_61E + male_62_64E + 
               female_20E + female_21E + female_22_24E + female_25_29E + female_30_34E + female_35_39E +
               female_40_44E +  female_45_49E + female_50_54E + female_55_59E + female_60_61E + female_62_64E,
             age_65_plus_count = male_65_66E + male_67_69E + male_70_74E + male_75_79E + male_80_84E + male_over_85E +
               female_65_66E + female_67_69E + female_70_74E + female_75_79E + female_80_84E + male_over_85E,
             age_under_20_perc = 100*age_under_20_count/age_total_count,
             age_20_64_perc = 100*age_20_64_count/age_total_count,
             age_65_plus_perc = 100*age_65_plus_count/age_total_count) %>%
      dplyr::select(geoid=GEOID,region_name=NAME,region_type,year,state_code,age_total_count,
                    age_under_20_count, age_20_64_count, age_65_plus_count,
                    age_under_20_perc, age_20_64_perc, age_65_plus_perc))
  }
  
  else if (topic=="Gender") {
    return(df %>% mutate(gender_total_count=total_popE,
                         gender_male_count = maleE, 
                         gender_female_count = femaleE,
                         gender_male_perc = 100*gender_male_count/gender_total_count,
                         gender_female_perc = 100*gender_female_count/gender_total_count) %>%
             dplyr::select(geoid=GEOID,region_name=NAME,region_type,year,state_code,gender_total_count,
                           gender_male_count,gender_female_count,gender_male_perc,
                           gender_female_perc))
    
  }
  else if (topic=="Language") {
    return(df %>% mutate(language_total_hh_count=total_hhE,
                         language_hh_limited_english_count = limited_english_spanishE + 
                           limited_english_indo_europeE + limited_english_asian_pacificE +
                           limited_english_other_languageE,
                         language_hh_limited_english_percent = 100*
                           (language_hh_limited_english_count)/language_total_hh_count) %>%
             dplyr::select(geoid=GEOID,region_name=NAME,region_type,year,state_code,
                           language_hh_limited_english_count,language_hh_limited_english_percent))
  }
  else if (topic=="Race") {
    return(df %>% mutate(race_total_count=total_raceE,pop_wht_alone = wht_aloneE, 
                           race_afr_amer_alone_count = afr_amer_aloneE, 
                           race_native_alone_count = native_aloneE, 
                           race_AAPI_count = (asian_aloneE + pacific_islander_aloneE), 
                           race_other_count = other_languageE, pop_two_or_more = two_or_moreE,
                           race_hispanic_or_latino_count = pop_hispanic_or_latinoE,
                           race_wht_alone_count = 100*pop_wht_alone/total_race,
                           race_afr_amer_alone_perc = 100*race_afr_amer_alone_count/race_total_count,
                           race_native_alone_perc = 100*race_native_alone_count/race_total_count,
                           race_AAPI_perc = 100*race_AAPI_count/race_total_count,
                           race_two_or_more_perc = 100*race_two_or_more_count/race_total_count,
                           race_other_perc = 100*race_other_count/race_total_count,
                           race_hispanic_or_latino_perc = 100*race_hispanic_or_latino_count/pop_eth_totE) %>%
             dplyr::select(geoid=GEOID,region_name=NAME,region_type,year,state_code,
                           race_total_count,race_wht_alone_count,race_afr_amer_alone_count,
                           race_native_alone_count,race_AAPI_alone_count,
                           race_other_count,race_two_or_more_count,
                           race_hispanic_or_latino_count,race_wht_alone_perc,race_afr_amer_alone_perc,
                           race_native_alone_perc,race_AAPI_perc,race_two_or_more_perc,
                           race_other_perc,race_hispanic_or_latino_perc))
  }
  else if (topic=="Veteran") {
    return (df %>% mutate(veteran_count = num_vetE, veteran_perc = 100*num_vetE/vet_denomE)%>%
            dplyr::select(geoid=GEOID,region_name=NAME,region_type,year,state_code,veteran_count,veteran_perc))
  }
  
}

format_acs <- function(topic, raw_df) {
  #' formats raw acs data based on demographic distributions for a given topic 
  #' param: topic(character) -> acs topic
  #' param: raw_df(dataframe) -> raw acs data to format
  #' return: formatted(dataframe) -> formatted acs data

  formatted <- calc_distribution(topic, raw_df) %>%
    gather(measure, value, -c(geoid, region_name, region_type, year, state_code)) %>%
    select(geoid,region_name,region_type,year,measure,value,state_code) %>%
    mutate(moe='', census_year=if_else(year<2020,2010,2020)) %>%
    mutate(geoid=format(geoid, scientific = FALSE, justify='none')) %>%
    filter(!is.na(value)) 
  
  return(formatted)
}

get_current_stored <- function(filepath, filename) {
  #' gets current data from filepath if exists
  #' param: filepath(character) -> path to check
  #' param: filename(character) -> file to check for
  #' return: current data as dataframe if exists. else NULL
  return(file.exists(paste0(filepath, filename)))
}

get_existing_acs_data <- function(filepath, filename, topic, states, 
                                  geographies, years, topic_vars_dict) {
  #' determines what acs data is not already stored
  #' param: filepath(character) -> path to check
  #' param: filename(character) -> file to check for
  #' param: topic(character) -> acs topic requested
  #' param: states(character vector) -> states requested
  #' param: geographies(character vector) ->geographies requested
  #' param: years(numeric vector) -> range of years requested
  #' param: topic_vars_dict(named character list of vectors) -> specifies 
  #'                 wanted acs topics and corresponding topic variables. maps
  #'                 topic to list of variables. 
  #' return: 
  
  
}

ingest <- function(topic, states, geographies, years, variables, force=FALSE) {
  #' downloads census demographic data for a given topic
  #' param: topic(character) -> topic to grab acs data for
  #' param: states(character list) -> list of state codes - states to grab 
  #'                                  aggregate data on
  #' param: geographies(character list) -> list of geographies to grab
  #' param: years(numeric list) -> range of years to grab
  #' param: variables(character list) -> acs variables to include
  #' param: force(boolean - default FALSE) -> if TRUE, reingests all acs data 
  #'                                          requested. else, searches for 
  #'                                          existing data and updates existing
  #' return: acs(dataframe) -> acs data filtered for topic, states, geographies, 
  #'                           and years

  
  # download data for states specified
  acs_raw <- NULL
  for (state in states){
    for (geo in geographies){
      for (year in years){
        if ((geo=='block group') && (year<2013)){
          temp <- NULL
        }else{
          temp <- data.table::setDT(
            tidycensus::get_acs(
              state = state,
              survey = "acs5",
              year = year,
              geography = geo,
              output = "wide",
              variables = variables
            )
          )
          
          # store state, geography, and year for data pulled
          temp$year <- year
          temp$region_type <- geo
          temp$state_code <- state
          
          acs_raw<- rbind(acs_raw, temp)
        }
      }
    }
  }
  
  return(acs_raw)
}

# TODO: is there a way to check which geographies are already part of acs? can i just run try on all geographies passed?
get_geography_demographics_data <- function(states, geographies, years, 
                                            topic_vars, models, savepaths, 
                                            force=FALSE) {
  #' gets demographics data for given geographies. non-acs geographies are 
  #' calculated using specified methods/models.
  #' param: states(character vector) -> two letter state codes for the states
  #'                 to grab demographic data for
  #' param: geographies(character vector) -> geographies to get data on
  #' param: years(numeric vector) -> range of years to get data on
  #' param: topic_vars_dict(named character list of vectors) -> specifies 
  #'                 wanted acs topics and corresponding topic variables. maps
  #'                 topic to list of variables. 
  #' param: models(character list) -> models for calculating non-acs geographies
  #' param: savepath(character) -> path to save acs data to 
  #' param: ncr(boolean - default FALSE) -> whether to get data on the 
  #'                 national capital region
  #' param: force(boolean - default FALSE) -> if TRUE, reingests all acs data 
  #'                 requested. else, searches for existing data and updates
  #'                 existing
  #' return: NONE -> saves a compressed csv file(s)
  source("main/working/constants.R")
  
  for (topic in topics) {
    if (ingest) {
      # get acs data 
      acs_orig <- ingest(topic, if_else(ncr, unique(c(states, 'VA', 'MD', 'DC')), states), 
                    geographies, years, vars[[topic]])
      acs <- format_acs(topic, acs_orig)
      
      # get acs data for each specified state
      state_acs_dct <- list()
      for (state in states) {
        state_acs <- get_state(acs, acs$state_code, state)
        state_acs_dct <- list(state_acs_dct, state = state_acs)
      }
      
      # if ncr, get national capital region
      if (ncr) {
        ncr_acs <- get_ncr(acs)
        
        # add methods to ncr measures (for website control)
        ncr_acs <- duplicate(ncr_acs, models)
        
        # save ncr data
        saveas <- (paste0(savepath,"ncr_cttrbg_acs_", min(years),'_',max(years),
                          '_', topic, '_demographics.csv.xz'))
        readr::write_csv(ncr_acs, xzfile(saveas, compression = 9))
      }


    }
    
  }
  
}


