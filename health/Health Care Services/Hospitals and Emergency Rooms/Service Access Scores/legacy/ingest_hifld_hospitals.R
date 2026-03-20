library(sf)
library(data.table)
library(jsonlite)

hifld_hospitals <- sf::read_sf(
  "https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/Hospitals_1/FeatureServer/0/query?where=1%3D1&outFields=*&outSR=4326&f=json"
)

hifld_hospitals$geometry <- NULL

sf::write_sf(hifld_hospitals, "Health Care Services/Hospitals and Emergency Rooms/Service Access Scores/data/original/us_hifld_2022_hospitals.csv")
