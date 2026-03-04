"Healthcare data was taken from the MEP Survey and Kaiser Family Foundation. 

From the MEPS, insurance premium as well as out-of-pocket cost data were collected. 
These data have vary according to the composition of a specific family. 
Specifically, different base costs are estimated depending on whether a household has 
one(single), two(employee-plus-one), or three+(family) people. 
However, these data are only granular down to the Census region level. 
Inflation adjustments needed to be applied to both the out-of-pocket and insurance premium 
costs since the data only exists up to 2021.

To better reflect more granular variation in healthcare costs, the Kaiser Family Foundation's 
2021 Health Insurance Marketplace Calculator was used. The numbers pulled from this calculator 
were those associated with the ACA's Silver Plan costs. The calculator allows for variation in 
family composition and for geographical variation down to the county level. 
The variation by county was used as an index to adjust the regional values obtained from 
the MEPS survey."

library(readxl)
library(sf)
library(dplyr)

va_tracts <- st_read("~/git/cost-living/data/Shapefile_VA_tract", int64_as_string = TRUE, stringsAsFactors = F)
va_tracts <- dplyr::select(as.data.frame(va_tracts), -geometry)[,c(1:2, 5)]
colnames(va_tracts) <- c("State", "County", "Tract")
va_tracts$GEOID <- paste0(va_tracts$State, va_tracts$County)
va_tracts <- va_tracts[,c(3, 4)]

healthcare_cost_by_county <- read_csv("~/git/cost-living/Health care cost/data/Working/us_ct_meps_kff_2019_2021_healthcarecost.csv")
healthcare_cost_by_county$GEOID <- as.character(healthcare_cost_by_county$fips)
healthcare_cost_by_county <- healthcare_cost_by_county[,-c(1:5)]
healthcare_cost_by_county <- left_join(va_tracts, healthcare_cost_by_county, by="GEOID")

write.csv(healthcare_cost_by_county,"~/git/cost-living/Health care cost/data/Working/va_tr_meps_kff_2019_2021_healthcarecost.csv")
