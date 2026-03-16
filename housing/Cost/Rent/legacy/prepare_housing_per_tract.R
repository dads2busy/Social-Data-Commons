"Sources of Data: Housing costs are obtained from the HUD 
<https://www.huduser.gov/portal/datasets/fmr.html#2023>, 
specifically from the table for 2023 Small Area Fair Market Rates (ZIP Code level) 
for tracts lying in metropolitan areas and from the table for 2023 Fair Market Rates 
(County level) for those tracts not lying in metropolitan areas. 
Fair Market Rates are defined as the 40th percentile of monthly rental costs in a given area. 
The values for tracts in metropolitan areas were attained by taking the mean value across 
the rental costs for each ZIP code which they intersected. 
The values for tracts not in metropolitan areas were attained by having the tract inherit 
the county level rate. 

Fair Market Rates and Small Area Fair Market Rates are given for 0-bedroom (studio), 
1-bedroom, 2-bedroom, 3-bedroom, and 4-bedroom apartments. We assume that a single person 
will live in a 0-bedroom apartment. Beyond that, we assume that each bedroom will contain 
up to two adults or two children but not one child and one adult (who would require 
two separate bedrooms)."

library(dplyr)
library(sf)
library(tigris)
library(readxl)
library(xlsx)

virginia_tracts <- read_sf("~/sdc.housing/data/housing_rent/original/virginia_tracts/virginia_tracts.shp", stringsAsFactors=FALSE)
fy2023_safmrs_revised <- read_xlsx("~/git/cost-living/Housing cost/data/Original/fy2023_safmrs.xlsx")

fy2023_safmrs_revised <- fy2023_safmrs_revised[,-c(2,3,5,6,8,9,11,12,14,15,17,18)]
colnames(fy2023_safmrs_revised)[1] <- "zip"
zip_tract_crosswalk_2020 <- read.csv("~/git/cost-living/Housing cost/data/Working/housing-Donovan/zip_tract_crosswalk_2020.csv")

zip_tract_crosswalk_2020$zip <- as.character(zip_tract_crosswalk_2020$zip)
fy2023_safmrs_revised <- left_join(zip_tract_crosswalk_2020, fy2023_safmrs_revised, by = "zip")

housing_per_tract <- unique(virginia_tracts[,4])
housing_per_tract <- dplyr::select(as.data.frame(housing_per_tract), -geometry)
housing_per_tract$rent_0br <- 0
housing_per_tract$rent_1br <- 0
housing_per_tract$rent_2br <- 0
housing_per_tract$rent_3br <- 0
housing_per_tract$rent_4br <- 0

colnames(fy2023_safmrs_revised) <- c("X", "tract", "zip", "b0","b1","b2","b3","b4")

for (i in 1:length(housing_per_tract$GEOID)){
  rent_0 <- 0
  rent_1 <- 0
  rent_2 <- 0
  rent_3 <- 0
  rent_4 <- 0
  count <- 0
  for (j in 1:length(fy2023_safmrs_revised$tract)){
    if (as.numeric(housing_per_tract$GEOID[i]) == fy2023_safmrs_revised$tract[j]){
      rent_0 <- rent_0 + fy2023_safmrs_revised$b0[j]
      rent_1 <- rent_1 + fy2023_safmrs_revised$b1[j]
      rent_2 <- rent_2 + fy2023_safmrs_revised$b2[j]
      rent_3 <- rent_3 + fy2023_safmrs_revised$b3[j]
      rent_4 <- rent_4 + fy2023_safmrs_revised$b4[j]
      count <- count + 1}
  }
  if (count > 0){
    housing_per_tract[i,2] <- rent_0/count
    housing_per_tract[i,3] <- rent_1/count
    housing_per_tract[i,4] <- rent_2/count
    housing_per_tract[i,5] <- rent_3/count
    housing_per_tract[i,6] <- rent_4/count}
}

housing_per_tract$GEOID <- as.numeric(housing_per_tract$GEOID)

housing_per_tract_ffx <- housing_per_tract %>%
  filter(substr(GEOID, 1, 5) == "51059")
housing_county <- read_excel("~/git/cost-living/Housing cost/data/Original/FY23_FMRs.xlsx")
housing_county$fips <- substr(housing_county$fips, 1, 5)
housing_county <- housing_county %>%
  filter(substr(fips,1,2) == '51')
housing_county$fips <- as.numeric(housing_county$fips)
housing_county <- housing_county[,c(2,11,12,13,14,15)]

housing_per_tract$fips <- as.numeric(substr(housing_per_tract$GEOID, 1, 5))
housing_per_tract <- left_join(housing_per_tract, housing_county, by = 'fips')

housing_per_tract$rent_0br <- ifelse( is.na(housing_per_tract$rent_0br), housing_per_tract$fmr_0 , housing_per_tract$rent_0br  )
housing_per_tract$rent_1br <- ifelse( is.na(housing_per_tract$rent_1br), housing_per_tract$fmr_1 , housing_per_tract$rent_1br  )
housing_per_tract$rent_2br <- ifelse( is.na(housing_per_tract$rent_2br), housing_per_tract$fmr_2 , housing_per_tract$rent_2br  )
housing_per_tract$rent_3br <- ifelse( is.na(housing_per_tract$rent_3br), housing_per_tract$fmr_3 , housing_per_tract$rent_3br  )
housing_per_tract$rent_4br <- ifelse( is.na(housing_per_tract$rent_4br), housing_per_tract$fmr_4 , housing_per_tract$rent_4br  )

housing_per_tract <- housing_per_tract[,-c(7:12)]

write.xlsx(housing_per_tract, "~/git/cost-living/Housing cost/data/Working/housing-Donovan/va_tr_hud_2022_housing_cost_imputations.xlsx")
write.xlsx(housing_per_tract_ffx, "~/git/cost-living/Housing cost/data/Working/housing-Donovan/va059_tr_hud_2022_housing_cost_imputations.xlsx")
