# get data on women's health conditions: mammograms, cervical cancer screening,
#     older women who are up to date on preventative services
# data from: https://data.cdc.gov/500-Cities-Places/PLACES-Local-Data-for-Better-Health-Census-Tract-D/cwsq-ngmh

library(dplyr)
library(ggplot2)
library(sf)

# sourcing tract standardization function (currently on my branch)
source("~/git/sdc.geographies_dev/utils/distribution/tract_conversions.R")

va_geo <- sf::st_read("https://raw.githubusercontent.com/uva-bi-sdad/sdc.geographies/main/VA/Census%20Geographies/Tract/2020/data/distribution/va_geo_census_cb_2020_census_tracts.geojson") %>%
  filter(startsWith(geoid, '51059'))

df <- read.csv("Population Health/Women's Health/data/PLACES_Census_Tract_Data_2023.csv.xz",
               colClasses = c(CountyFIPS='character', LocationName='character'))

# fairfax, health conditions relevant to women only
fairfax <- df %>% filter(StateAbbr=="VA", CountyName=="Fairfax", Measure %in%
                           c("Cervical cancer screening among adult women aged 21-65 years",
                             "Mammography use among women aged 50-74 years",
                             "Older adult women aged >=65 years who are up to date on a core set of clinical preventive services: Flu shot past year, PPV shot ever, Colorectal cancer screening, and Mammogram past 2 years")) 

# convert to 2020 tracts 
converted <- NULL
for (measure in c("CERVICAL", "COREW", "MAMMOUSE")) {
  temp <- fairfax %>% filter(MeasureId==measure) %>% 
    select(geoid=LocationName, value=Data_Value)
  temp <- convert_2010_to_2020_bounds(temp)
  temp <- merge(temp, va_geo, by='geoid', all.y=TRUE) %>% 
    mutate(value = ifelse(value < 1, NA, value),
           MeasureId = measure)
  
  converted <- rbind(converted, temp)
}

# mapping by 2020 tract polygons (using 2010-2020 converted data) --------------
ffx_map <- st_as_sf(converted)

cervical_map <- ffx_map %>% filter(MeasureId=="CERVICAL")
corew_map <- ffx_map %>% filter(MeasureId=="COREW")
mammo_map <- ffx_map %>% filter(MeasureId=="MAMMOUSE")

ggplot() +
  scale_fill_gradientn(colors = c("yellow", "orange", "brown"), name="Percent Screening") +
  geom_sf(data = cervical_map, mapping=aes(fill=value)) +
  ggtitle("Percent Cervical Cancer Screening \nAmong Adult Women Aged 21-65 Years")

ggplot() +
  scale_fill_gradientn(colours = c("yellow", "orange", "brown"), name="Percent Up to Date") +
  geom_sf(data=corew_map, mapping=aes(fill=value)) + 
  ggtitle("Older Adult Women Aged >= 65 Years \nWho Are Up to Date on a \nCore Set of Clinical Preventive Services")

ggplot() +
  scale_fill_gradientn(colours = c("yellow", "orange", "brown"), name="Percent Use") +
  geom_sf(data=mammo_map, mapping=aes(fill=value)) + 
  ggtitle("Mammography use among women aged 50-74 years")

ggplot(ffx_map, aes(x=value)) + geom_density() + facet_grid('MeasureId') + xlab('percent')

# mapping by initial coordinates provided -------------------------------------
ffx_coords <- st_as_sf(fairfax, wkt='Geolocation', crs=4326) 
ggplot(ffx_coords, aes(x=Data_Value)) + geom_density() + facet_grid('MeasureId') + xlab('percent')

cervical_coords <- ffx_coords %>% filter(MeasureId=="CERVICAL")
corew_coords <- ffx_coords %>% filter(MeasureId=="COREW")
mammo_coords <- ffx_coords %>% filter(MeasureId=="MAMMOUSE")

ggplot() +
  scale_colour_gradientn(colours = c("yellow", "orange", "brown"), name="Percent Screening") +
  geom_sf(data = va_geo, fill = "darkgrey") +
  geom_sf(data=cervical_coords, mapping=aes(color=Data_Value)) + 
  ggtitle("Percent Cervical Cancer Screening \nAmong Adult Women Aged 21-65 Years")

ggplot() +
  scale_colour_gradientn(colours = c("yellow", "orange", "brown"), name="Percent Up to Date") +
  geom_sf(data = va_geo, fill = "darkgrey") +
  geom_sf(data=corew_coords, mapping=aes(colour=Data_Value)) + 
  ggtitle("Older Adult Women Aged >= 65 Years \nWho Are Up to Date on a \nCore Set of Clinical Preventive Services")

ggplot() +
  scale_colour_gradientn(colours = c("yellow", "orange", "brown"), name="Percent Use") +
  geom_sf(data = va_geo, fill = "darkgrey") +
  geom_sf(data=mammo_coords, mapping=aes(colour=Data_Value)) + 
  ggtitle("Mammography use among women aged 50-74 years")

readr::write_csv(fairfax, xzfile("Population Health/Women's Health/data/fairfax_womens_health_data.csv.xz", 
                                 compression = 9))
