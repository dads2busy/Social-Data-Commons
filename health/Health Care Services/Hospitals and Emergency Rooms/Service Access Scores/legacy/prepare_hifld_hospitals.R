library(data.table)
us_hifld <- fread("Health Care Services/Hospitals and Emergency Rooms/Service Access Scores/data/original/us_hifld_2022_hospitals.csv")
va_hifld <- us_hifld[STATE=="VA"]

options(scipen=999)

# extract and set year from epoch date (millisecond)
va_hifld$SOURCEDATE_YEAR <-
  format(as.POSIXct(as.numeric(va_hifld$SOURCEDATE / 1000), origin = "1970-01-01"), format = "%Y")

unique(va_hifld$SOURCEDATE_YEAR)

