library(data.table)

# 2017 CMS Doctors
file_paths <- dataplumbr::file.download_unzip2temp("https://data.cms.gov/provider-data/sites/default/files/archive/Doctors%20and%20clinicians/2017/doc_archive_12_2017.zip")
file_path <- file_paths[file_paths %like% "National"]
dt <- data.table::fread(file_path, select = c("NPI", "Last Name", "First Name", "Gender", "Credential", "Primary specialty", "Secondary specialty 1", "Secondary specialty 2", "Line 1 Street Address", "Line 2 Street Address", "City", "State", "Zip Code"))
dt_vadcmd <- dt[State %in% c("VA", "DC", "MD") & Credential %in% c("MD", "DO") & (`Primary specialty` == "OBSTETRICS/GYNECOLOGY" | `Secondary specialty 1` == "OBSTETRICS/GYNECOLOGY" | `Secondary specialty 2` == "OBSTETRICS/GYNECOLOGY")]
data.table::fwrite(dt_vadcmd, "Health Care Services/Physicians/OB-GYN/Service Access Scores/data/original/vadcmd_cms_2017_obgyn.csv", append = FALSE)

# 2018 CMS Doctors
file_paths <- dataplumbr::file.download_unzip2temp("https://data.cms.gov/provider-data/sites/default/files/archive/Doctors%20and%20clinicians/2018/doc_archive_12_2018.zip")
file_path <- file_paths[file_paths %like% "\\.csv"]
dt <- data.table::fread(file_path, select = c("NPI", "lst_nm", "frst_nm", "gndr", "Cred", "pri_spec", "sec_spec_1", "sec_spec_2", "adr_ln_1", "adr_ln_2", "cty", "st", "zip"))
dt_vadcmd <- dt[st %in% c("VA", "DC", "MD") & Cred %in% c("MD", "DO") & (pri_spec == "OBSTETRICS/GYNECOLOGY" | sec_spec_1 == "OBSTETRICS/GYNECOLOGY" | sec_spec_2 == "OBSTETRICS/GYNECOLOGY")]
data.table::fwrite(dt_vadcmd, "Health Care Services/Physicians/OB-GYN/Service Access Scores/data/original/vadcmd_cms_2018_obgyn.csv", append = FALSE)

# 2019 CMS Doctors
file_paths <- dataplumbr::file.download_unzip2temp("https://data.cms.gov/provider-data/sites/default/files/archive/Doctors%20and%20clinicians/2019/doc_archive_12_2019.zip")
file_path <- file_paths[file_paths %like% "\\.csv"]
dt <- data.table::fread(file_path, select = c("NPI", "lst_nm", "frst_nm", "gndr", "Cred", "pri_spec", "sec_spec_1", "sec_spec_2", "adr_ln_1", "adr_ln_2", "cty", "st", "zip"))
dt_vadcmd <- dt[st %in% c("VA", "DC", "MD") & Cred %in% c("MD", "DO") & (pri_spec == "OBSTETRICS/GYNECOLOGY" | sec_spec_1 == "OBSTETRICS/GYNECOLOGY" | sec_spec_2 == "OBSTETRICS/GYNECOLOGY")]
data.table::fwrite(dt_vadcmd, "Health Care Services/Physicians/OB-GYN/Service Access Scores/data/original/vadcmd_cms_2019_obgyn.csv", append = FALSE)

# 2020 CMS Doctors
file_paths <- dataplumbr::file.download_unzip2temp("https://data.cms.gov/provider-data/sites/default/files/archive/Doctors%20and%20clinicians/2020/doctors_and_clinicians_archive_12_2020.zip")
file_path <- file_paths[file_paths %like% "\\.csv"]
dt <- data.table::fread(file_path, select = c("NPI", "lst_nm", "frst_nm", "gndr", "Cred", "pri_spec", "sec_spec_1", "sec_spec_2", "adr_ln_1", "adr_ln_2", "cty", "st", "zip"))
dt_vadcmd <- dt[st %in% c("VA", "DC", "MD") & Cred %in% c("MD", "DO") & (pri_spec == "OBSTETRICS/GYNECOLOGY" | sec_spec_1 == "OBSTETRICS/GYNECOLOGY" | sec_spec_2 == "OBSTETRICS/GYNECOLOGY")]
data.table::fwrite(dt_vadcmd, "Health Care Services/Physicians/OB-GYN/Service Access Scores/data/original/vadcmd_cms_2020_obgyn.csv", append = FALSE)

# 2021 CMS Doctors
file_paths <- dataplumbr::file.download_unzip2temp("https://data.cms.gov/provider-data/sites/default/files/archive/Doctors%20and%20clinicians/2021/doctors_and_clinicians_12_2021.zip")
file_path <- file_paths[file_paths %like% "National"]
dt <- data.table::fread(file_path, select = c("NPI", "lst_nm", "frst_nm", "gndr", "Cred", "pri_spec", "sec_spec_1", "sec_spec_2", "adr_ln_1", "adr_ln_2", "cty", "st", "zip"))
dt_vadcmd <- dt[st %in% c("VA", "DC", "MD") & Cred %in% c("MD", "DO") & (pri_spec == "OBSTETRICS/GYNECOLOGY" | sec_spec_1 == "OBSTETRICS/GYNECOLOGY" | sec_spec_2 == "OBSTETRICS/GYNECOLOGY")]
data.table::fwrite(dt_vadcmd, "Health Care Services/Physicians/OB-GYN/Service Access Scores/data/original/vadcmd_cms_2021_obgyn.csv", append = FALSE)

# 2022 CMS Doctors
file_paths <- dataplumbr::file.download_unzip2temp("https://data.cms.gov/provider-data/sites/default/files/archive/Doctors%20and%20clinicians/2022/doctors_and_clinicians_12_2022.zip")
file_path <- file_paths[file_paths %like% "National"]
dt <- data.table::fread(file_path, select = c("NPI", "lst_nm", "frst_nm", "gndr", "Cred", "pri_spec", "sec_spec_1", "sec_spec_2", "adr_ln_1", "adr_ln_2", "cty", "st", "zip"))
dt_vadcmd <- dt[st %in% c("VA", "DC", "MD") & Cred %in% c("MD", "DO") & (pri_spec == "OBSTETRICS/GYNECOLOGY" | sec_spec_1 == "OBSTETRICS/GYNECOLOGY" | sec_spec_2 == "OBSTETRICS/GYNECOLOGY")]
data.table::fwrite(dt_vadcmd, "Health Care Services/Physicians/OB-GYN/Service Access Scores/data/original/vadcmd_cms_2022_obgyn.csv", append = FALSE)
