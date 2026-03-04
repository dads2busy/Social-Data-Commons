#imputation using nearby counties

va_tr_meps_kff_2019_2023_healthcarecost <- read.csv("/Users/avagutshall/Desktop/folder/sdc.health_dev/Health care cost/data/Working/va_tr_meps_kff_2019_2023_healthcarecost.csv")  # if it's a CSV

for (i in 1:length(va_tr_meps_kff_2019_2023_healthcarecost$GEOID)){
  if (va_tr_meps_kff_2019_2023_healthcarecost$GEOID[i] == 51760){
    va_tr_meps_kff_2019_2023_healthcarecost[i, 4:11] <- va_tr_meps_kff_2019_2023_healthcarecost[502, 4:11]
  }
  if (va_tr_meps_kff_2019_2023_healthcarecost$GEOID[i] == 51600){
    va_tr_meps_kff_2019_2023_healthcarecost[i, 4:11] <- va_tr_meps_kff_2019_2023_healthcarecost[5, 4:11]
  }
  if (va_tr_meps_kff_2019_2023_healthcarecost$GEOID[i] == 51620){
    va_tr_meps_kff_2019_2023_healthcarecost[i, 4:11] <- va_tr_meps_kff_2019_2023_healthcarecost[266, 4:11]
  }
  if (va_tr_meps_kff_2019_2023_healthcarecost$GEOID[i] == 51161){
    va_tr_meps_kff_2019_2023_healthcarecost[i, 4:11] <- va_tr_meps_kff_2019_2023_healthcarecost[655, 4:11]
  }
}

write.csv(va_tr_meps_kff_2019_2021_healthcarecost, "/Users/avagutshall/Desktop/folder/sdc.health_dev/Health care cost/data/Working/va_tr_meps_kff_2019_2023_healthcarecost_imputed.csv")
