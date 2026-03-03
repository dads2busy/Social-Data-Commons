# assign each companies to a census block group using adress, county, zipcode, longitude and latitude


# Library
library(readr)
library(dplyr)
library(stringr)
library(tigris)
library(sf)
library(data.table)
library(ggplot2)
library(tidygeocoder)


# upload mergent intellect companies details data ----------------------------------------------------------------------------
path = "Microdata/Mergent_intellect/data/working/"
mi <-  read_csv(paste0(path,"mi_companies_details.csv.xz"))


# subset to fairfax county companies and select the main variables -----------------------------------------------------------
temp_fairfax <- mi %>% 
  filter(`Physical County`=='FAIRFAX') %>% 
  select(company_name=`Company Name`, 
         duns = `D-U-N-S@ Number`, 
         address= `Physical Address`, 
         county= `Physical County`, 
         city=`Physical City`, 
         zipcode=`Physical Zipcode`, 
         state = `Physical State`,
         primary_naics = `Primary NAICS Code`,
         Latitude, 
         Longitude=Longtitude)


# method 1: use the lon and lat infos provides by mergent intellect and build geometry --------------------
temp_fairfax_sf <- st_as_sf(temp_fairfax, coords = c("Longitude", "Latitude"), crs = 4269, agr = "constant") 




# method2: use googlemap api to geolocate companies (get lon and lat using address) ----------------------
temp_fairfax_sf$full_address <- paste(
  str_trim(temp_fairfax_sf$address),
  str_trim(temp_fairfax_sf$county),
  str_trim(temp_fairfax_sf$city),
  str_trim(temp_fairfax_sf$zipcode),
  str_trim(temp_fairfax_sf$state))

# remove white spaces
temp_fairfax_sf$full_address <- str_squish(temp_fairfax_sf$full_address)

# installed google api key
readRenviron("~/.Renviron")
Sys.getenv("google_api_key")

register_google(key = Sys.getenv("google_api_key"), write = TRUE)
test1 <- mutate_geocode(temp_fairfax_sf, location = full_address, output = "latlona")

#geocode the addresses
temp1 <- temp_fairfax_sf %>%
  geocode(full_address,
          method = 'google',
          lat = latitude ,
          long = longitude,
          full_results = T)

# get the geometry based on the latitude and longitude
temp_fairfax_sf <- st_as_sf(temp1, coords = c("longitude", "latitude"), crs = 4269, agr = "constant") 



# method3: the data may already exist just get it ---------------------------------------------------------
if (("mi_fairfax_google_geo.csv.xz" %in% list.files("Microdata/Mergent_intellect/data/working/"))){
  path = "Microdata/Mergent_intellect/data/working/"
  temp_fairfax <-  read_csv(paste0(path,"mi_fairfax_google_geo.csv.xz")) %>%
    select(company_name, duns, address, formatted_address, county, city, zipcode, state, latitude, longitude) %>%
    mutate(longitude=if_else(is.na(longitude),0,longitude),
           latitude=if_else(is.na(latitude),0,latitude))
}

# get the geometry based on the latitude and longitude
temp_fairfax_sf <- st_as_sf(temp_fairfax, coords = c("longitude", "latitude"), crs = 4269, agr = "constant") 




# Assign each companies to a census blocks using lat and lon ---------------------------------------------------------------------------------

# get the census block group for Fairfax county (countyid = 51059)
fairfax_bg2010 <- read_sf('https://github.com/uva-bi-sdad/sdc.geographies/blob/ead00ea3cdf7992ff4cba8f29656a0914f67a070/VA/Census%20Geographies/Block%20Group/2010/data/distribution/va_geo_census_cb_2010_census_block_groups.geojson?raw=T') %>%
  select(geoid,region_name,region_type,year) %>% filter(substr(geoid,1,5)=='51059')
fairfax_bg2020 <- read_sf('https://github.com/uva-bi-sdad/sdc.geographies/blob/ead00ea3cdf7992ff4cba8f29656a0914f67a070/VA/Census%20Geographies/Block%20Group/2020/data/distribution/va_geo_census_cb_2020_census_block_groups.geojson?raw=T') %>%
  select(geoid,region_name,region_type,year)  %>% filter(substr(geoid,1,5)=='51059')


# assign each company to a census block group (cautious about the census year of those block)
temp_ncr_bg2010 <- st_join(st_transform(fairfax_bg2010,4269), temp_fairfax_sf, left=F, join=st_intersects) %>% st_drop_geometry() %>% select(company_name,duns,geoid,region_name,region_type)
temp_ncr_bg2020 <- st_join(st_transform(fairfax_bg2020,4269), temp_fairfax_sf, left=F, join=st_intersects) %>% st_drop_geometry() %>% select(company_name,duns,geoid,region_name,region_type)  


# save the data ------------------------------------------------------------------------------------
readr::write_csv(temp_ncr_bg2010, xzfile(paste0(path,"mi_fairfax_geolocated_bg2010.csv.xz"), compression = 9))
readr::write_csv(temp_ncr_bg2020, xzfile(paste0(path,"mi_fairfax_geolocated_bg2020.csv.xz"), compression = 9))



