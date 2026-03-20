file_paths <- list.files("Health Care Services/Physicians/Primary Care/Service Access Scores/data/original/", 
                         pattern = "*primary*", 
                         full.names = TRUE)

if(exists("dt_all")) rm("dt_all")
for (f in file_paths) {
  yr <- stringr::str_extract(f, "20[0-9][0-9]")
  dt <- data.table::fread(f, select = c(1:13), colClasses = "character")
  dt[,1][[1]] <- as.numeric(dt[,1][[1]])
  dt$year <- yr
  if(exists("dt_all")) {
    dt_all <- data.table::rbindlist(list(dt_all, dt), use.names=TRUE)
  } else {
    dt_all <- dt
  }
}

colnames(dt_all) <- c("npi",
                      "last_name",
                      "first_name",
                      "gender",
                      "credential",
                      "primary_specialty",
                      "secondary_specialty_1",
                      "secondary_specialty_2",
                      "address_line_1",
                      "address_line_2",
                      "city",
                      "state",
                      "postalcode",
                      "year")

data.table::fwrite(dt_all, "Health Care Services/Physicians/Primary Care/Service Access Scores/data/working/vadcmd_cms_2018_2022_primary_care_physicians.csv", append = FALSE)
