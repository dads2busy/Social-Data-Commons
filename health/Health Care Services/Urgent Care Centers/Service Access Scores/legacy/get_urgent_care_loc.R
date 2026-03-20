# packages
library(httr)
library(jsonlite)
library(RPostgreSQL)
library(dplyr)

geo2fips <- function(latitude, longitude) {
  url <- "https://geo.fcc.gov/api/census/area?lat=%f&lon=%f&format=json"
  block <- jsonlite::fromJSON(sprintf(url, latitude, longitude))[["results"]][["block_fips"]]
  block
}

res <- GET("https://opendata.arcgis.com/datasets/335ccc7c0684453fad69d8a64bc89192_0.geojson")

data = fromJSON(rawToChar(res$content))

# fields
unique_ID <- data$features$properties$ID
facility_name <- data$features$properties$NAME
phone <- data$features$properties$TELEPHONE
address <- data$features$properties$ADDRESS
address2 <- data$features$properties$ADDRESS2
city <- data$features$properties$CITY
state <- data$features$properties$STATE
zip <- data$features$properties$ZIP
zip4 <- data$features$properties$ZIPP4
county <- data$features$properties$COUNTY
fips <- data$features$properties$FIPS
directions <- data$features$properties$DIRECTIONS
naics_code <- data$features$properties$NAICSCODE
naics_descr <- data$features$properties$NAICSDESCR
lat <- data$features$properties$Y
lon <- data$features$properties$X
geo_precision <- data$features$properties$GEOPREC

# to df and save 
hifld_urgent_care <- data.frame(unique_ID, 
                        facility_name,
                        phone, 
                        address, 
                        address2,
                        city, 
                        state, 
                        zip, 
                        zip4,
                        county, 
                        fips, 
                        directions,
                        naics_code, 
                        naics_descr,
                        lat, 
                        lon, 
                        geo_precision)

# get Virginia
hifld_urgent_care_VA <- subset(hifld_urgent_care, state == "VA")

VA_geoids <- apply(hifld_urgent_care_VA,
                   1,
                   function(x) geo2fips(as.numeric(x[15]), 
                                        as.numeric(x[16])))

hifld_urgent_care_VA$block_geoid <- VA_geoids
hifld_urgent_care_VA$bg_geoid <- substr(hifld_urgent_care_VA$block_geoid, 1, 12)
hifld_urgent_care_VA$tract_geoid <- substr(hifld_urgent_care_VA$block_geoid, 1, 11)
hifld_urgent_care_VA$cnty_geoid <- substr(hifld_urgent_care_VA$block_geoid, 1, 5)

#write.csv(hifld_urgent_care_VA, 
#          file = "/project/biocomplexity/sdad/projects_data/mc/data_commons/dc_health_behavior_diet/HIFLD/urgent_care/urgent_care_loc_VA_122021.csv",
#          row.names = FALSE)

# get Maryland
hifld_urgent_care_MD <- subset(hifld_urgent_care, state == "MD")

MD_geoids <- apply(hifld_urgent_care_MD,
                   1,
                   function(x) geo2fips(as.numeric(x[15]), 
                                        as.numeric(x[16])))

hifld_urgent_care_MD$block_geoid <- MD_geoids
hifld_urgent_care_MD$bg_geoid <- substr(hifld_urgent_care_MD$block_geoid, 1, 12)
hifld_urgent_care_MD$tract_geoid <- substr(hifld_urgent_care_MD$block_geoid, 1, 11)
hifld_urgent_care_MD$cnty_geoid <- substr(hifld_urgent_care_MD$block_geoid, 1, 5)

#write.csv(hifld_urgent_care_MD, 
#          file = "/project/biocomplexity/sdad/projects_data/mc/data_commons/dc_health_behavior_diet/HIFLD/urgent_care/urgent_care_loc_MD_122021.csv",
#          row.names = FALSE)

# get DC
hifld_urgent_care_DC <- subset(hifld_urgent_care, state == "DC")

DC_geoids <- apply(hifld_urgent_care_DC,
                   1,
                   function(x) geo2fips(as.numeric(x[15]), 
                                        as.numeric(x[16])))

hifld_urgent_care_DC$block_geoid <- DC_geoids
hifld_urgent_care_DC$bg_geoid <- substr(hifld_urgent_care_DC$block_geoid, 1, 12)
hifld_urgent_care_DC$tract_geoid <- substr(hifld_urgent_care_DC$block_geoid, 1, 11)
hifld_urgent_care_DC$cnty_geoid <- substr(hifld_urgent_care_DC$block_geoid, 1, 5)

#write.csv(hifld_urgent_care_DC, 
#          file = "/project/biocomplexity/sdad/projects_data/mc/data_commons/dc_health_behavior_diet/HIFLD/urgent_care/urgent_care_loc_DC_122021.csv",
#          row.names = FALSE)


### NCR Region urgent care ###
capital_region_df <- read.csv("/project/biocomplexity/sdad/projects_data/mc/data_commons/capital_regions_df.csv")

hifld_urgent_care_ncr <- rbind(hifld_urgent_care_VA, hifld_urgent_care_DC, hifld_urgent_care_MD)

hifld_urgent_care_ncr <- hifld_urgent_care_ncr %>%
  filter(cnty_geoid %in% capital_region_df$cnty_fips) %>%
  as.data.frame()


# write data to db
conn <- dbConnect(drv = PostgreSQL(), 
                  dbname = "sdad", 
                  host = "10.250.124.195", 
                  port = 5432, 
                  user = Sys.getenv(x = "db_userid"), 
                  password = Sys.getenv(x = "db_pwd")
)

# write to data commons database, auto-detect if writing geom or not, change owner to data_commons
dc_dbWriteTable <-
  function(
    db_conn,
    schema_name,
    table_name,
    table_data,
    table_owner = "data_commons"
  ) {
    # check for geometry/geography columns
    tf <- sapply(table_data, {function(x) inherits(x, 'sfc')})
    # if TRUE, use sf
    if (TRUE %in% tf) {
      sf_write_result <- sf::st_write(obj = table_data, dsn = db_conn, layer = c(schema_name, table_name), row.names = FALSE)
      print(sf_write_result)
      # if FALSE, use DBI
    } else {
      write_result <- DBI::dbWriteTable(conn = db_conn, name = c(schema_name, table_name), value = table_data, row.names = FALSE)
      print(write_result)
    }
    # change table owner
    chgown_result <- DBI::dbSendQuery(conn = db_conn, statement = paste0("ALTER TABLE ", schema_name, ".", table_name, " OWNER TO ", table_owner))
    print(chgown_result)
  }

dc_dbWriteTable(conn,
                "dc_health_behavior_diet",
                "va_pl_hifld_2021_urgent_care",
                hifld_urgent_care_VA,
                "data_commons")

dc_dbWriteTable(conn,
                "dc_health_behavior_diet",
                "dc_pl_hifld_2021_urgent_care",
                hifld_urgent_care_DC,
                "data_commons")

dc_dbWriteTable(conn,
                "dc_health_behavior_diet",
                "md_pl_hifld_2021_urgent_care",
                hifld_urgent_care_MD,
                "data_commons")

dc_dbWriteTable(conn,
                "dc_health_behavior_diet",
                "ncr_pl_hifld_2021_urgent_care",
                hifld_urgent_care_ncr,
                "data_commons")

dbDisconnect(conn)

