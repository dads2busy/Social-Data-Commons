#Code for creating ZIP-Tract Crosswalk with 2020 boundaries
library(dplyr)
library(sf)
library(tigris)
library(readxl)
virginia_tracts <- read_sf("~/git/cost-living/data/Shapefile_VA_tr/cb_2021_51_tract_500k.shp", stringsAsFactors=FALSE)
zip_codes <- read_sf("~/git/cost-living/data/ZCTA_Shapefiles/tl_2021_us_zcta520.shp", stringsAsFactors = FALSE)


sf_use_s2(FALSE)
# get US state shapefile
states <- st_as_sf(states())
va <- states[53,]
zip_codes <- zip_codes %>%
  filter(st_intersects(zip_codes$geometry, va$geometry, sparse = FALSE))

zip_tract_crosswalk_2020 <- data.frame(matrix(NA, nrow = 0, ncol = 2))

count = 0
for (i in 1:length(virginia_tracts$TRACTCE)){
  if (i%%100 == 0){print(i)}
  for (j in 1:length(zip_codes$ZCTA5CE20)){
    if (st_intersects(zip_codes$geometry[j], virginia_tracts$geometry[i], sparse = FALSE)){
      count <- count + 1
      zip_tract_crosswalk_2020[count,] <- c(virginia_tracts$GEOID[i], zip_codes$ZCTA5CE20[j])
    }
  }
}

colnames(zip_tract_crosswalk_2020) <- c("tract", "zip")

write.csv(zip_tract_crosswalk_2020,"~/zip_tract_crosswalk_2020.csv")

zip_tract_ffx <- zip_tract_crosswalk_2020 %>%
  filter(substr(tract, 1, 5) == "51059")

write.csv(zip_tract_ffx,"~/git/cost-living/Housing cost/data/Working/housing-Donovan/zip_tract_ffx.csv")