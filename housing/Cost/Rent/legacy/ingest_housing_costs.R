library(xlsx)
library(readxl)

download.file("https://www.huduser.gov/portal/datasets/fmr/fmr2023/FY23_FMRs.xlsx", destfile = "/tmp/FY23_FMRs.xlsx")
write.xlsx(readxl::read_excel("/tmp/FY23_FMRs.xlsx"), "~/git/cost-living/Housing cost/data/Original/FY23_FMRs.xlsx")

download.file("https://www.huduser.gov/portal/datasets/fmr/fmr2023/fy2023_safmrs.xlsx", destfile = "/tmp/fy2023_safmrs.xlsx")
write.xlsx(readxl::read_excel("/tmp/fy2023_safmrs.xlsx"), "~/git/cost-living/Housing cost/data/Original/fy2023_safmrs.xlsx")
