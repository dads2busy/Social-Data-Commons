file_paths <- list.files("Health Care Services/Hospitals and Emergency Rooms/Service Access Scores/data/original/", 
                         pattern = "cms_hospitals_20", 
                         full.names = TRUE)

if(exists("dt_all")) rm("dt_all")
for (f in file_paths) {
  yr <- stringr::str_extract(f, "20[0-9][0-9]")
  dt <- data.table::fread(f, select = c(1:11), colClasses = "character")
  dt[,1][[1]] <- as.numeric(dt[,1][[1]])
  dt$year <- yr
  if(exists("dt_all")) {
    dt_all <- data.table::rbindlist(list(dt_all, dt), use.names=FALSE)
  } else {
    dt_all <- dt
  }
}

colnames(dt_all) <- c("facility_id",
                      "facility_name",
                      "address",
                      "city",
                      "state",
                      "zip_code",
                      "county_name",
                      "phone_number",
                      "hospital_type",
                      "hospital_ownership",
                      "emergency_services",
                      "year")

dt_all$phone_number <- stringr::str_replace_all(dt_all$phone_number, pattern = "[ ()-]", replacement = "")
dt_all$county_name <- trimws(toupper(dt_all$county_name))

data.table::fwrite(dt_all, "Health Care Services/Hospitals and Emergency Rooms/Service Access Scores/data/working/us_cms_2015_2022_hospitals.csv", append = FALSE)
