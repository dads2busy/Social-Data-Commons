library(tidygeocoder)
library(magrittr)

us_cms_hospitals <- data.table::fread("Health Care Services/Hospitals and Emergency Rooms/Service Access Scores/data/working/us_cms_2015_2022_hospitals.csv")


vadcmd_cms_hospitals <- us_cms_hospitals[state=="VA" | state=="DC" | state=="MD"]
vadcmd_cms_hospitals[county_name == "THE DISTRICT", county_name := "DISTRICT OF COLUMBIA"]
vadcmd_cms_hospitals[county_name == "SAINT MARYS", county_name := "ST. MARY'S"]
vadcmd_cms_hospitals[county_name == "ST. MARYS", county_name := "ST. MARY'S"]
vadcmd_cms_hospitals[county_name == "PRINCE GEORGES", county_name := "PRINCE GEORGE'S"]
vadcmd_cms_hospitals[county_name == "SALEM", county_name := "SALEM CITY"]


va_counties <- tigris::list_counties("VA")
va_counties$county_code <- paste0("51", va_counties$county_code)
va_counties$state <- "VA"

dc_counties <- tigris::list_counties("DC")
dc_counties$county_code <- paste0("11", dc_counties$county_code)
dc_counties$state <- "DC"

md_counties <- tigris::list_counties("MD")
md_counties$county_code <- paste0("24", md_counties$county_code)
md_counties$state <- "MD"

vadcmd_counties <- data.table::rbindlist(list(
  va_counties, dc_counties, md_counties
)) 

vadcmd_counties$county <- trimws(toupper(vadcmd_counties$county))

mrg <- merge(vadcmd_cms_hospitals, vadcmd_counties, by.x = c("county_name", "state"), by.y = c("county", "state"), all.x = TRUE)

nrc_cms_hospitals <- mrg[county_code %in% c("51013", "51059", "51107", "51510", "51600", "51153", "51683", "51685", "51610", "11001", "24031", "24033", "24017", "24021")]
# c("51013", "51059", "51107", "51510", "51600", "51153", "51683", "51685", "51610", "11001", "24031", "24033", "24017", "24021")


tbl <- data.table(street = nrc_cms_hospitals$address,
                  city = nrc_cms_hospitals$city,
                  state = nrc_cms_hospitals$state,
                  postalcode = nrc_cms_hospitals$zip_code)
tbl_unq <- unique(tbl)
tbl_unq$address <- paste(tbl_unq$street, tbl_unq$city, tbl_unq$state, tbl_unq$postalcode)

# geocode(tbl, street = street, city = city, state = state, postalcode = postalcode, method = "osm")

cascade_results1 <- tbl_unq %>%
  geocode_combine(
    queries = list(
      list(method = 'census'),
      list(method = 'arcgis'),
      list(method = 'osm')
    ),
    global_params = list(address = 'address')
  )

data.table::setDT(cascade_results1)

mrg <- merge(nrc_cms_hospitals, cascade_results1, by.x = c("address", "city", "state", "zip_code"), by.y = c("street", "city", "state", "postalcode"))

nrc_cms_2015_2022_hospitals <- mrg[, .(facility_id, 
                                      facility_name, 
                                      year, 
                                      lat, 
                                      long,
                                      address, 
                                      city, 
                                      state, 
                                      zip_code, 
                                      county_name, 
                                      phone_number, 
                                      hospital_type, 
                                      hospital_ownership, 
                                      emergency_services 
)]

data.table::fwrite(nrc_cms_2015_2022_hospitals, "Health Care Services/Hospitals and Emergency Rooms/Service Access Scores/data/working/ncr_cms_2015_2022_hospitals.csv")
