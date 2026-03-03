# EDA

# libraries 
library(readr)
library(dplyr)
library(stringr)
library(tigris)
library(sf)
library(data.table)
library(ggplot2)
library(reshape2)
library(crosstable)
library(tidyr)
library(scales)
library(readr)
library(cowplot)
library(ggpubr)
library(tidyverse)


# 1. trends in mainority owned business

path = "Business_characteristics/Minority_owned/data/distribution/"
# upload the data --------------------------------------------------------------------
business <-  read_csv(paste0(path,"va059_cttrbg_mi_2010_2020_number_business_by_minority.csv.xz"))

# extract the metric and category, select one census geo-levels, filter of year >2011, count of all businesses 
category <- c('minority_owned_','non_minority_owned_')
temp <- business %>%
  mutate(metrics=str_remove_all(measure, paste(category, collapse = "|")),
         category=str_remove_all(measure, paste(unique(metrics), collapse = "|")),
         metrics=str_replace_all(metrics,'_',' '),
         category=str_replace_all(category, '_', ' '),
         ngeoid=nchar(geoid)) %>%
  filter(ngeoid==5) %>%
  filter(year>2010) %>%
  group_by(year,category) %>%
  summarize(value=sum(value, na.rm=T))


test <- temp %>%
  pivot_wider(names_from = 'category', values_from=value) %>%
  mutate(total_num = `minority owned ` + `non minority owned `,
         share=100*`minority owned `/total_num)


# fig 1: Distribution of Fairfax businesses over time by minority status
plt1 <- temp %>%
  ggplot(aes(factor(year), value, fill=category)) +   
  geom_bar(stat = "identity", colour="black")+
  scale_fill_manual(values=c("#920000","#009999")) +
  labs(x = "year", y="Number companies listed in Fairfax county") +
  theme(axis.text.y = element_text(size=14))
plt1


# Data treatment
path="Microdata/Mergent_intellect/data/working/"
mi_fairfax_features <-  read_csv(paste0(path,"mi_fairfax_features_bg.csv.xz"))

# build the data (count of business by industry and category) - similar data need to be build in the repo
temp_business_bg <-  mi_fairfax_features %>%
  mutate(type=if_else(minority==1,'minority_owned','non_minority_owned')) %>%
  group_by(geoid,year,naics_name,type) %>%
  summarize(measure='number_business',
            value=length(duns)) %>%
  mutate(measure=paste0(type,'_',naics_name,'_',measure),
         measure_type='count',
         moe='') %>%
  ungroup() %>%
  select(geoid,year,measure,value,measure_type,moe)


temp_emp_bg <-  mi_fairfax_features %>%
  mutate(type=if_else(minority==1,'minority_owned','non_minority_owned')) %>%
  group_by(geoid,year,naics_name,type) %>%
  summarize(measure='employment',
            value=sum(employment ,na.rm=T)) %>%
  mutate(measure=paste0(type,'_',naics_name,'_',measure),
         measure_type='count',
         moe='') %>%
  ungroup() %>%
  select(geoid,year,measure,value,measure_type,moe)




# data treatment -------------------------------------------------------
category <- c('minority_owned_','non_minority_owned_')
metrics <- c('number_business','employment')
temp_business <- temp_business_bg %>%
  mutate(res1=str_remove_all(measure, paste(metrics, collapse = "|")),
         industry=str_remove_all(res1, paste(category, collapse = "|")),
         category=str_remove(res1,fixed(industry)),
         metrics='number_business',
         industry=str_replace_all(industry,'_',''),
         category=str_replace_all(category, '_', ' ')
         ) %>%
  filter(year>2010) %>%
  group_by(year,industry,category) %>%
  summarize(value=sum(value, na.rm=T)) %>%
  pivot_wider(names_from='category', values_from='value') %>%
  mutate(total=`minority owned ` + `non minority owned `,
         minority=`minority owned `,
         perc_minority=100*minority/total) %>%
  select(year,industry,minority,perc_minority) %>%
  ungroup() %>%
  filter(year==2020) %>%
  filter(!is.na(minority)) %>%
  mutate(industry = fct_reorder(industry, minority))


temp_empl <- temp_emp_bg %>%
  mutate(res1=str_remove_all(measure, paste(metrics, collapse = "|")),
         industry=str_remove_all(res1, paste(category, collapse = "|")),
         category=str_remove(res1,fixed(industry)),
         metrics='employment',
         industry=str_replace_all(industry,'_',''),
         category=str_replace_all(category, '_', ' ')
  ) %>%
  filter(year>2010) %>%
  group_by(year,industry,category) %>%
  summarize(value=sum(value, na.rm=T)) %>%
  pivot_wider(names_from='category', values_from='value') %>%
  mutate(total=`minority owned ` + `non minority owned `,
         empl_minority=`minority owned `,
         perc_empl_minority=100*empl_minority/total) %>%
  select(year,industry,empl_minority,perc_empl_minority) %>%
  ungroup() %>%
  filter(year==2020) %>%
  filter(!is.na(empl_minority)) %>%
  mutate(industry = fct_reorder(industry, empl_minority))


# fig 2: - number of minority-owned companies by industry in 2020 - percentage of minority-owned companies by industry in 2020
temp_business01 <- temp_business %>% mutate(industry01=as.character(industry))
temp_business01[temp_business01$minority<107,]$industry01 <- 'Other industries'
temp_business01 <- temp_business01 %>%
  group_by(year,industry01) %>%
  summarise(minority=sum(minority),
         perc_minority=mean(perc_minority)) %>%
  mutate(industry01 = fct_reorder(industry01, minority),
         length=nchar(industry01),
         industry01=industry,
         industry01=paste0(substr(industry01,1,30),'...'))

plt2a <- temp_business01 %>%
  ggplot(aes(x='', minority, fill=industry01)) +   
  geom_bar(width = 1, stat = "identity")+
  labs(x = "Industry", y="Number of minority-owned companies in 2020") +
  coord_polar("y", start=0) +
  #coord_flip()+
  theme(axis.text.y = element_text(size=13)) +
  scale_fill_brewer(palette="Dark2")
plt2a

plt2b <-  temp_business01 %>%    
  ggplot(aes(industry01, perc_minority)) +   
  geom_bar(stat = "identity", fill="blue")+
  labs(x = "Industry", y="Percentage of minority-owned companies in 2020") +
  coord_flip()+
  theme(axis.text.y = element_text(size=13))
plt2b



# fig 3: - employment by minority-owned businesses by industry in 2020 - employment sharre of minority-owned companies by industry in 2020
plt3a <- temp_empl %>%
  ggplot(aes(industry, empl_minority)) +   
  geom_bar(stat = "identity", fill="blue")+
  labs(x = "Industry", y="Number of minority-owned companies in 2020") +
  coord_flip()+
  theme(axis.text.y = element_text(size=13))
plt3a

plt3b <- temp_empl %>%    
  ggplot(aes(industry, perc_empl_minority)) +   
  geom_bar(stat = "identity", fill="blue")+
  labs(x = "Industry", y="Percentage of minority-owned companies in 2020") +
  coord_flip()+
  theme(axis.text.y = element_text(size=13))
plt3b

# combine the graph
ggarrange(plt3a, 
          plt3b + theme(axis.text.y = element_blank(),
                        axis.ticks.y = element_blank(),
                        axis.title.y = element_blank() ), 
          nrow = 1,
          widths=c(2,1))





