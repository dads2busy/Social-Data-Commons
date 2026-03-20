library(tidygeocoder)
library(magrittr)

us_cms_hospitals <- data.table::fread("Health Care Services/Hospitals and Emergency Rooms/Service Access Scores/data/working/us_cms_2015_2022_hospitals.csv")
va_cms_hospitals <- us_cms_hospitals[state=="VA"]

tbl <- data.table(street = va_cms_hospitals$address,
                  city = va_cms_hospitals$city,
                  state = "VA",
                  postalcode = va_cms_hospitals$zip_code)
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

mrg <- merge(va_cms_hospitals, cascade_results1, by.x = c("address", "city", "state", "zip_code"), by.y = c("street", "city", "state", "postalcode"))

va_cms_2015_2022_hospitals <- mrg[, .(facility_id, 
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

data.table::fwrite(va_cms_2015_2022_hospitals, "Health Care Services/Hospitals and Emergency Rooms/Service Access Scores/data/working/va_cms_2015_2022_hospitals.csv")
