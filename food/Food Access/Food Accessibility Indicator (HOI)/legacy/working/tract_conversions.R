library(dplyr)

get_2010_2020_tract_changes <- function(tracts=NULL) {
  #' determines if/how census tract boundaries changed from 2010 to 2020. Adds
  #' an additional "type_change" column to 2010-2020 tract relationship file
  #' indicating whether a tract did not change ('same'), a tract was split but
  #' bounds did not change ('split'), or a tracts bounds moved ('moved').
  #' param: tracts(character vector - default NULL) -> tracts to get changes for.
  #'                                    if none provided, returns all of US
  #' return: dataframe of relationship data with "type_change" column.

  # get crosswalk data
  file_path <- 'https://www2.census.gov/geo/docs/maps-data/data/rel2020/tract/tab20_tract20_tract10_natl.txt'
  delimiter <- '|'

  crosswalk <- read.csv(file_path, sep=delimiter, colClasses=c("GEOID_TRACT_10"="character", "GEOID_TRACT_20"="character"))
  crosswalk <- crosswalk %>% select('GEOID_TRACT_20', 'GEOID_TRACT_10',
                                    'AREALAND_TRACT_20', 'AREALAND_TRACT_10',
                                    'AREALAND_PART') %>% filter(AREALAND_PART != 0)
  if(!is.null(tracts)) crosswalk <- crosswalk[crosswalk$GEOID_TRACT_10 %in% tracts, ]

  # determine if/how boundaries changed ---------------------------------------
  # get counts for 2010 and 2020 tract ids
  crosswalk <- crosswalk %>% group_by(GEOID_TRACT_20) %>%
    mutate(count_20 = n())
  crosswalk <- crosswalk %>% group_by(GEOID_TRACT_10) %>%
    mutate(count_10 = n())

  # Identifying tracts that are same
  tract_10_20 <- crosswalk %>% select(GEOID_TRACT_10, AREALAND_TRACT_20) %>%
    group_by(GEOID_TRACT_10) %>%
    summarise(AREALAND_TRACT_20 = sum(AREALAND_TRACT_20)) %>%
    select(GEOID_TRACT_10, match_area = AREALAND_TRACT_20)

  crosswalk <- left_join(crosswalk, tract_10_20, by='GEOID_TRACT_10')
  crosswalk <- crosswalk %>% mutate(type_change = case_when(
      count_10 == 1 & count_20 == 1 ~ 'same',
      AREALAND_TRACT_10 == match_area ~ 'split',
      TRUE ~ 'moved'
    )) %>% select(-c(count_10, count_20, match_area)) %>% 
    ungroup() 

  return(crosswalk)
}

convert_2010_to_2020_tracts <- function(data, geoid_col='geoid', val_col='value') {
  #' redistributes 2010 data based on 2020 census tract boundaries
  #' param: data(dataframe) -> data to redistribute. contains geoid(2010) and value attributes.
  #' param: geoid_col(character - default='geoid') -> name of column with 2010 geoids
  #' return: redistributed(dataframe) -> data redistributed to 2020 tract boundaries.
  #'            contains geoids(2020) and redistributed values
  
  tracts <- unique(data[,geoid_col])
  
  if (class(data[, geoid_col]) != 'character') {
    stop("geoids should be characters")
  }
  if (length(data[, geoid_col]) > length(tracts)) {
    stop("geoids are not unique -- data cannot contain more than one entry per geoid. 
         please double check that data only spans one year, measure, etc.")
  }
  
  # standardize data naming
  data <- data[, c(geoid_col, val_col)]
  names(data)[names(data) == val_col] <- 'value'
  
  options(scipen = 999)

  # get relationship data

  crosswalk <- get_2010_2020_tract_changes(tracts)

  # join data with crosswalk
  # for 2010 tracts that are split, data gets distributed to each new tract
  joined <- crosswalk %>% left_join(data, by=c('GEOID_TRACT_10' = geoid_col))

  # case when tract borders don't change (same or split), no more changes necessary
  same_bounds <- data.frame(joined)[joined$type_change=='same' | joined$type_change=='split', ]  %>%
    group_by(GEOID_TRACT_20) %>% summarise(value=first(value))

  # case when borders are moved
  moved_bounds <- joined[joined$type_change == 'moved', ]

  # calculate weighted mean based on percent overlap
  moved_bounds <- moved_bounds %>%
    mutate(pct_overlap = AREALAND_PART / AREALAND_TRACT_20) %>%
    mutate(value = value * pct_overlap)%>%
    group_by(GEOID_TRACT_20) %>%
    summarise(value = sum(value)) 

  # bind two cases
  redistributed <- rbind(same_bounds, moved_bounds) %>% 
    rename(geoid=GEOID_TRACT_20) 
  View(redistributed)
  colnames(data)[names(data) == 'value'] <- val_col

  return(redistributed)
}
