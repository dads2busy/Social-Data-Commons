

geodatadir <- "../../data/projects_data/usda/bb/original/geo/"
map_program_area_cc <- st_read(file.path(geodatadir, "CC 2013_2019_83 04272020.shp")) %>%
  sf::st_transform(4326)

con <- get_db_conn(db_host = "localhost", db_port = 5434)

sf::st_write(map_program_area_cc, con, c("usda_bb", "cc_program_areas"), delete_layer = TRUE)
DBI::dbDisconnect(con)