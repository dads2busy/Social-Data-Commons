
# 2015 CMS Hospitals
file_paths <- dataplumbr::file.download_unzip2temp("https://data.cms.gov/provider-data/sites/default/files/archive/Hospitals/2015/hos_revised_flatfiles_archive_12_2015.zip")
file_path <- file_paths[file_paths %like% "General"]
dt <- data.table::fread(file_path)
data.table::fwrite(dt, "Health Care Services/Hospitals and Emergency Rooms/Service Access Scores/data/original/cms_hospitals_2015.csv")

# 2016 CMS Hospitals
file_paths <- dataplumbr::file.download_unzip2temp("https://data.cms.gov/provider-data/sites/default/files/archive/Hospitals/2016/hos_revised_flatfiles_archive_12_2016.zip")
file_path <- file_paths[file_paths %like% "General"]
dt <- data.table::fread(file_path)
data.table::fwrite(dt, "Health Care Services/Hospitals and Emergency Rooms/Service Access Scores/data/original/cms_hospitals_2016.csv")

# 2017 CMS Hospitals
file_paths <- dataplumbr::file.download_unzip2temp("https://data.cms.gov/provider-data/sites/default/files/archive/Hospitals/2017/hos_revised_flatfiles_archive_10_2017.zip")
file_path <- file_paths[file_paths %like% "General"]
dt <- data.table::fread(file_path)
data.table::fwrite(dt, "Health Care Services/Hospitals and Emergency Rooms/Service Access Scores/data/original/cms_hospitals_2017.csv")

# 2018 CMS Hospitals
file_paths <- dataplumbr::file.download_unzip2temp("https://data.cms.gov/provider-data/sites/default/files/archive/Hospitals/2018/hos_revised_flatfiles_archive_10_2018.zip")
file_path <- file_paths[file_paths %like% "General"]
dt <- data.table::fread(file_path)
data.table::fwrite(dt, "Health Care Services/Hospitals and Emergency Rooms/Service Access Scores/data/original/cms_hospitals_2018.csv")

# 2019 CMS Hospitals
file_paths <- dataplumbr::file.download_unzip2temp("https://data.cms.gov/provider-data/sites/default/files/archive/Hospitals/2019/hos_revised_flatfiles_archive_10_2019.zip")
file_path <- file_paths[file_paths %like% "General"]
dt <- data.table::fread(file_path)
data.table::fwrite(dt, "Health Care Services/Hospitals and Emergency Rooms/Service Access Scores/data/original/cms_hospitals_2019.csv")

# 2020 CMS Hospitals
file_paths <- dataplumbr::file.download_unzip2temp("https://data.cms.gov/provider-data/sites/default/files/archive/Hospitals/2020/hos_revised_flatfiles_archive_04_2020.zip")
file_path <- file_paths[file_paths %like% "General"]
dt <- data.table::fread(file_path)
data.table::fwrite(dt, "Health Care Services/Hospitals and Emergency Rooms/Service Access Scores/data/original/cms_hospitals_2020.csv")

# 2021 CMS Hospitals
file_paths <- dataplumbr::file.download_unzip2temp("https://data.cms.gov/provider-data/sites/default/files/archive/Hospitals/2021/hospitals_10_2021.zip")
file_path <- file_paths[file_paths %like% "General"]
dt <- data.table::fread(file_path)
data.table::fwrite(dt, "Health Care Services/Hospitals and Emergency Rooms/Service Access Scores/data/original/cms_hospitals_2021.csv")

# 2022 CMS Hospitals
file_paths <- dataplumbr::file.download_unzip2temp("https://data.cms.gov/provider-data/sites/default/files/archive/Hospitals/2022/hospitals_10_2022.zip")
file_path <- file_paths[file_paths %like% "General"]
dt <- data.table::fread(file_path)
data.table::fwrite(dt, "Health Care Services/Hospitals and Emergency Rooms/Service Access Scores/data/original/cms_hospitals_2022.csv")



