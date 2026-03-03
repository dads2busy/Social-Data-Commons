#other expenses


source("~/git/cost-living/code/cost_of_living_budget/4_source_files/source_merge_dfcoltic.R")

percentage_other_expenses <- 0.2

df_col_tic <- df_col_tic %>% mutate(other_month = (food_cost_month+housing_cost_month)*percentage_other_expenses )
