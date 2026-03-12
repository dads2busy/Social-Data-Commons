dir <- "data/meps/original/"
dir.create(dir, FALSE)

# Medical Expenditure Panel Survey (MEPS) Panel 23 Longitudinal file
meps_zip <- paste0(dir, "h217xlsx.zip")
meps_file <- paste0(dir, "h217.xlsx")
if (!file.exists(meps_file)) {
  if (!file.exists(meps_zip)) download.file("https://www.meps.ahrq.gov/mepsweb/data_files/pufs/h217/h217xlsx.zip", meps_zip)
  unzip(meps_zip, exdir = dir)
  unlink(meps_zip)
}
