library(data.table)

# 2018 CMS Doctors
rm(dt)
rm(dt_vadcmd)
file_paths <- dataplumbr::file.download_unzip2temp("https://data.cms.gov/provider-data/sites/default/files/archive/Doctors%20and%20clinicians/2018/doc_archive_12_2018.zip")
file_path <- file_paths[file_paths %like% "\\.csv"]
dt <- data.table::fread(file_path, select = c("NPI", "lst_nm", "frst_nm", "gndr", "Cred", "pri_spec", "sec_spec_1", "sec_spec_2", "adr_ln_1", "adr_ln_2", "cty", "st", "zip"))
dt_vadcmd <- dt[st %in% c("VA", "DC", "MD") & Cred %in% c("MD", "DO") & (pri_spec %in% c("FAMILY PRACTICE", "FAMILY MEDICINE", "GENERAL PRACTICE") | sec_spec_1 %in% c("FAMILY PRACTICE", "FAMILY MEDICINE", "GENERAL PRACTICE") | sec_spec_2 %in% c("FAMILY PRACTICE", "FAMILY MEDICINE", "GENERAL PRACTICE"))]
data.table::fwrite(dt_vadcmd, "Health Care Services/Physicians/Primary Care/Service Access Scores/data/original/vadcmd_cms_2018_primary.csv", append = FALSE)

# 2019 CMS Doctors
rm(dt)
rm(dt_vadcmd)
file_paths <- dataplumbr::file.download_unzip2temp("https://data.cms.gov/provider-data/sites/default/files/archive/Doctors%20and%20clinicians/2019/doc_archive_12_2019.zip")
file_path <- file_paths[file_paths %like% "\\.csv"]
dt <- data.table::fread(file_path, select = c("NPI", "lst_nm", "frst_nm", "gndr", "Cred", "pri_spec", "sec_spec_1", "sec_spec_2", "adr_ln_1", "adr_ln_2", "cty", "st", "zip"))
dt_vadcmd <- dt[st %in% c("VA", "DC", "MD") & Cred %in% c("MD", "DO") & (pri_spec %in% c("FAMILY PRACTICE", "FAMILY MEDICINE", "GENERAL PRACTICE") | sec_spec_1 %in% c("FAMILY PRACTICE", "FAMILY MEDICINE", "GENERAL PRACTICE") | sec_spec_2 %in% c("FAMILY PRACTICE", "FAMILY MEDICINE", "GENERAL PRACTICE"))]
data.table::fwrite(dt_vadcmd, "Health Care Services/Physicians/Primary Care/Service Access Scores/data/original/vadcmd_cms_2019_primary.csv", append = FALSE)

# 2020 CMS Doctors
rm(dt)
rm(dt_vadcmd)
file_paths <- dataplumbr::file.download_unzip2temp("https://data.cms.gov/provider-data/sites/default/files/archive/Doctors%20and%20clinicians/2020/doctors_and_clinicians_archive_12_2020.zip")
file_path <- file_paths[file_paths %like% "\\.csv"]
dt <- data.table::fread(file_path, select = c("NPI", "lst_nm", "frst_nm", "gndr", "Cred", "pri_spec", "sec_spec_1", "sec_spec_2", "adr_ln_1", "adr_ln_2", "cty", "st", "zip"))
dt_vadcmd <- dt[st %in% c("VA", "DC", "MD") & Cred %in% c("MD", "DO") & (pri_spec %in% c("FAMILY PRACTICE", "FAMILY MEDICINE", "GENERAL PRACTICE") | sec_spec_1 %in% c("FAMILY PRACTICE", "FAMILY MEDICINE", "GENERAL PRACTICE") | sec_spec_2 %in% c("FAMILY PRACTICE", "FAMILY MEDICINE", "GENERAL PRACTICE"))]
data.table::fwrite(dt_vadcmd, "Health Care Services/Physicians/Primary Care/Service Access Scores/data/original/vadcmd_cms_2020_primary.csv", append = FALSE)

# 2021 CMS Doctors
rm(dt)
rm(dt_vadcmd)
file_paths <- dataplumbr::file.download_unzip2temp("https://data.cms.gov/provider-data/sites/default/files/archive/Doctors%20and%20clinicians/2021/doctors_and_clinicians_12_2021.zip")
file_path <- file_paths[file_paths %like% "National"]
dt <- data.table::fread(file_path, select = c("NPI", "lst_nm", "frst_nm", "gndr", "Cred", "pri_spec", "sec_spec_1", "sec_spec_2", "adr_ln_1", "adr_ln_2", "cty", "st", "zip"))
dt_vadcmd <- dt[st %in% c("VA", "DC", "MD") & Cred %in% c("MD", "DO") & (pri_spec %in% c("FAMILY PRACTICE", "FAMILY MEDICINE", "GENERAL PRACTICE") | sec_spec_1 %in% c("FAMILY PRACTICE", "FAMILY MEDICINE", "GENERAL PRACTICE") | sec_spec_2 %in% c("FAMILY PRACTICE", "FAMILY MEDICINE", "GENERAL PRACTICE"))]
data.table::fwrite(dt_vadcmd, "Health Care Services/Physicians/Primary Care/Service Access Scores/data/original/vadcmd_cms_2021_primary.csv", append = FALSE)

# 2022 CMS Doctors
rm(dt)
rm(dt_vadcmd)
file_paths <- dataplumbr::file.download_unzip2temp("https://data.cms.gov/provider-data/sites/default/files/archive/Doctors%20and%20clinicians/2022/doctors_and_clinicians_12_2022.zip")
file_path <- file_paths[file_paths %like% "National"]
dt <- data.table::fread(file_path, select = c("NPI", "lst_nm", "frst_nm", "gndr", "Cred", "pri_spec", "sec_spec_1", "sec_spec_2", "adr_ln_1", "adr_ln_2", "cty", "st", "zip"))
dt_vadcmd <- dt[st %in% c("VA", "DC", "MD") & Cred %in% c("MD", "DO") & (pri_spec %in% c("FAMILY PRACTICE", "FAMILY MEDICINE", "GENERAL PRACTICE") | sec_spec_1 %in% c("FAMILY PRACTICE", "FAMILY MEDICINE", "GENERAL PRACTICE") | sec_spec_2 %in% c("FAMILY PRACTICE", "FAMILY MEDICINE", "GENERAL PRACTICE"))]
data.table::fwrite(dt_vadcmd, "Health Care Services/Physicians/Primary Care/Service Access Scores/data/original/vadcmd_cms_2022_primary.csv", append = FALSE)


