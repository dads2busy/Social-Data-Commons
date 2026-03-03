# assign each companies to a census block using adress, county, zipcode, longitude and latitude

# Library
library(readr)
library(dplyr)
library(stringr)
library(tigris)
library(sf)
library(data.table)
library(ggplot2)
library(tidygeocoder)
library(ggmap)


# upload the data --------------------------------------------------------------------------------
path = "Microdata/Mergent_intellect/data/working/"
companies <-  read_csv(paste0(path,"mi_companies_details.csv.xz"))


# data treatment ---------------------------------------------------------------------------------
# select the main variables 
temp <- companies %>% 
  select(company_name=`Company Name`, 
         duns = `D-U-N-S@ Number`, 
         address= `Physical Address`, 
         county= `Physical County`, 
         city=`Physical City`, 
         zipcode=`Physical Zipcode`, 
         state = `Physical State`,
         Latitude, 
         Longitude=Longtitude)

# filter to the main counties (richmond city, henrico and chesterfield)
area <- c('RICHMOND CITY', 'HENRICO','CHESTERFIELD')
temp_trunc <- temp %>%
  filter(county %in% area)


# method 1: use the lon and lat infos provides by mergent intellect and build geometry --------------------------------------
temp_sf <- st_as_sf(temp_trunc, coords = c("Longitude", "Latitude"), crs = 4269, agr = "constant") 


# method2: use googlemap api to geolocate companies (get lon and lat using address) ----------------------
temp_trunc$full_address <- paste(
  str_trim(temp_trunc$address),
  str_trim(temp_trunc$county),
  str_trim(temp_trunc$city),
  str_trim(temp_trunc$zipcode),
  str_trim(temp_trunc$state))

# remove white spaces
temp_trunc$full_address <- str_squish(temp_trunc$full_address)

# installed google api key
readRenviron("~/.Renviron")
Sys.getenv("google_api_key")

register_google(key = Sys.getenv("google_api_key"), write = TRUE)
test1 <- mutate_geocode(temp[1:10,], location = full_address, output = "latlona")

#geocode the addresses
temp1 <- temp_trunc[1:10,] %>%
  geocode(full_address,
          method = 'google',
          lat = latitude ,
          long = longitude,
          full_results = T)

temp_sf <- st_as_sf(temp_trunc, coords = c("Longitude", "Latitude"), crs = 4269, agr = "constant") 



# Assign each companies to a census block group: --------------------------------------
areaID = c('51159','51087','51041')

# get the census block group for the NCR
subva_bg2010 <- read_sf('https://github.com/uva-bi-sdad/sdc.geographies/blob/9bc22f9020c36a5a1007e866db2e3093cf91033d/VA/Census%20Geographies/Block%20Group/2010/data/distribution/va_geo_census_cb_2010_census_block_groups.geojson?raw=T') %>%
  select(geoid,region_name,region_type,year) %>%
  filter(substr(geoid,1,5) %in% areaID)

subva_bg2020 <- read_sf('https://github.com/uva-bi-sdad/sdc.geographies/blob/9bc22f9020c36a5a1007e866db2e3093cf91033d/VA/Census%20Geographies/Block%20Group/2020/data/distribution/va_geo_census_cb_2020_census_block_groups.geojson?raw=T') %>%
  select(geoid,region_name,region_type,year) %>%
  filter(substr(geoid,1,5) %in% areaID) 

# assign each company to a census block group using geometry for 2010 census bg and geometry for 2020 census bg
temp_subva_bg2010 <- st_join(st_transform(subva_bg2010,4269), temp_sf, left=F, join=st_intersects) %>% st_drop_geometry() %>% select(company_name,duns,geoid,region_name,region_type)
temp_subva_bg2020 <- st_join(st_transform(subva_bg2020,4269), temp_sf, left=F, join=st_intersects) %>% st_drop_geometry() %>% select(company_name,duns,geoid,region_name,region_type)  


# save the data ------------------------------------------------------------------------------------
readr::write_csv(temp_subva_bg2010, xzfile(paste0(path,"mi_subva_geolocated_bg2010.csv.xz"), compression = 9))
readr::write_csv(temp_subva_bg2020, xzfile(paste0(path,"mi_subva_geolocated_bg2020.csv.xz"), compression = 9))




