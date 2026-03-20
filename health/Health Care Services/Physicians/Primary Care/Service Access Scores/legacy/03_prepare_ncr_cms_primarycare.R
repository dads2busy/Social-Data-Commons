library(tidygeocoder)
library(magrittr)
library(data.table)

vadcmd_cms_primarycare <- data.table::fread("Health Care Services/Physicians/Primary Care/Service Access Scores/data/working/vadcmd_cms_2018_2022_primary_care_physicians.csv")


tbl <- data.table(npi = vadcmd_cms_primarycare$npi,
                  street = vadcmd_cms_primarycare$address_line_1,
                  city = vadcmd_cms_primarycare$city,
                  state = vadcmd_cms_primarycare$state,
                  postalcode = vadcmd_cms_primarycare$postalcode)
tbl_unq <- unique(tbl)
tbl_unq$address <- paste(tbl_unq$street, tbl_unq$city, tbl_unq$state, tbl_unq$postalcode)


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

data.table::fwrite(cascade_results1, file = "Health Care Services/Physicians/Primary Care/Service Access Scores/data/working/vadcmd_cms_2018_2022_primary_care_physicians_geo_tmp.csv")

results_geo_tmp <- data.table::fread("Health Care Services/Physicians/Primary Care/Service Access Scores/data/working/vadcmd_cms_2018_2022_primary_care_physicians_geo_tmp.csv")

dt_fcc <- data.table(npi = character(), county_fips = character(), county_name = character())
for (i in 1:nrow(results_geo_tmp)) {
  url <- paste0("https://geo.fcc.gov/api/census/block/find?latitude=", results_geo_tmp[i]$lat, "&longitude=", results_geo_tmp[i]$long,
                "&censusYear=2020&format=json")
  json <- jsonlite::read_json(url)
  dt <- data.table::data.table(npi = cascade_results1$npi[i], county_fips = json$County$FIPS, county_name = json$County$name)
  dt_fcc <- data.table::rbindlist(list(dt_fcc, dt))
  print(paste(i, json$County$FIPS))
}

results_geo_tmp$npi <-  as.character(results_geo_tmp$npi)

dt_fcc_unq <- unique(dt_fcc)

mrg <- merge(results_geo_tmp, dt_fcc_unq, by = "npi", all.x = TRUE)

ncr_cms_2018_2022_primary_care_physicians <- mrg[county_fips %in% c("51013", "51059", "51107", "51510", "51600", "51153", "51683", "51685", "51610", "11001", "24031", "24033", "24017", "24021")]


nrc_cms_2015_2022_primary_care_physicians <- mrg[, .(facility_id, 
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

data.table::fwrite(nrc_cms_2015_2022_primary_care_physicians, "Health Care Services/Physicians/Primary Care/Service Access Scores/data/working/nrc_cms_2015_2022_primary_care_physicians.csv")






json_tmp <- jsonlite::read_json("https://geo.fcc.gov/api/census/block/find?latitude=38.90714&longitude=-76.83734&censusYear=2020&format=json")
