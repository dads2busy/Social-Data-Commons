# Analyze the entry rate, exit rate, job creation and job destruction by minority owned business


# library
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
library(cowplot)
library(ggpubr)



# Entry and Exit rate ------------------------------------------------------------------------------------------

# load the data
uploadpath = "Business_characteristics/Minority_owned/data/distribution/"
industry <-  read_csv(paste0(uploadpath,"va059_ct_mi_20102020_minority_industry_profile.csv.xz"))

# all minority-owned businesses
type <- c('minority_owned','non_minority_owned')
metrics <- c('total_business','new_business','exit_business','entry_rate','exit_rate')

temp <- industry %>%
  filter(measure_type=='count') %>%
  mutate(industry=str_remove_all(str_remove_all(measure, paste(type, collapse = "|")),paste(metrics, collapse = "|")),
         metrics=str_remove_all(str_remove_all(measure, paste(type, collapse = "|")),paste(industry, collapse = "|")),
         type=str_remove_all(str_remove_all(measure, paste(industry, collapse = "|")),paste(metrics, collapse = "|"))) %>%
  filter(type=='minority_owned') %>%
  filter(metrics %in% c('total_business','new_business','exit_business')) %>%
  filter(year %in% 2011:2020) %>%
  group_by(year,metrics) %>%
  summarise(value=sum(value, na.rm=T)) %>%
  pivot_wider(names_from=metrics, values_from=value) %>%
  mutate(new_business=replace(new_business, year==2011, NA),
         exit_business=replace(exit_business, year==2020, NA),
         entry_rate=100*new_business/total_business,
         exit_rate=100*exit_business/total_business)

plt1 <- ggplot(temp, aes(x=factor(year), y=total_business)) +   
  geom_bar(stat = "identity", fill="black") +
  ylim(0,6000) +
  labs(title="Number of Minority-Owned Businesses over Time", x ="Year", y="number of businesses") +
  theme(plot.title = element_text(size=14),legend.title = element_text(size=10),axis.title.x = element_text(size=12),axis.title.y = element_text(size=12))

plt2 <- ggplot(temp, aes(x=year)) + 
  geom_line(aes(y = entry_rate, color = "entry rate")) + 
  geom_line(aes(y = 10*exit_rate, color="exit rate")) +
  scale_x_continuous(breaks= pretty_breaks()) +
  scale_y_continuous(name = "entry rate (%)", sec.axis = sec_axis(~.*.1, name="exit rate (%)")) +
  labs(title="Entry and Exit rate among Minority-Owned Businesses", x ="Year", color = "") +
  theme(legend.position = 'bottom',plot.title = element_text(size=14),legend.title = element_text(size=10),axis.title.x = element_text(size=12),axis.title.y = element_text(size=12)) +
  scale_color_manual(values = c("navy", "red"))

plt <- ggarrange(plt1, plt2, nrow = 1)
plt

ggsave("/home/yhu2bk/Github/fig/entry_exit_dynamism.png", plt)




# select a specific industry: Professional, scientific, and technical services
type <- c('minority_owned','non_minority_owned')
metrics <- c('total_business','new_business','exit_business','entry_rate','exit_rate','number_business')

temp <- industry %>%
  filter(measure_type=='count') %>%
  mutate(industry=str_remove_all(str_remove_all(measure, paste(type, collapse = "|")),paste(metrics, collapse = "|")),
         metrics=str_remove_all(str_remove_all(measure, paste(type, collapse = "|")),paste(industry, collapse = "|")),
         type=str_remove_all(str_remove_all(measure, paste(industry, collapse = "|")),paste(metrics, collapse = "|")),
         industry=str_replace_all(industry,'_',' ')) %>%
  filter(industry==' Professional, Scientific, and Technical Services ') %>%
  filter(type=='minority_owned') %>%
  filter(metrics %in% c('total_business','new_business','exit_business')) %>%
  filter(year %in% 2011:2020) %>%
  group_by(year,metrics) %>%
  summarise(value=sum(value, na.rm=T)) %>%
  pivot_wider(names_from=metrics, values_from=value) %>%
  mutate(new_business=replace(new_business, year==2011, NA),
         exit_business=replace(exit_business, year==2020, NA),
         entry_rate=100*new_business/total_business,
         exit_rate=100*exit_business/total_business)


plt1a <- ggplot(temp, aes(x=factor(year), y=total_business)) +   
  geom_bar(stat = "identity", fill="black") +
  labs(title="Number of Minority-Owned Businesses over Time", x ="Year", y="number of businesses") +
  theme(plot.title = element_text(size=14),legend.title = element_text(size=10),axis.title.x = element_text(size=12),axis.title.y = element_text(size=12))

plt2a <- ggplot(temp, aes(x=year)) + 
  geom_line(aes(y = entry_rate, color = "entry rate")) + 
  geom_line(aes(y = 10*exit_rate, color="exit rate")) +
  scale_x_continuous(breaks= pretty_breaks()) +
  scale_y_continuous(
    name = "entry rate (%)",
    sec.axis = sec_axis(~.*.1, name="exit rate (%)")) +
  labs(title="Entry and Exit rate among Minority-Owned Businesses", x ="Year", color = "") +
  theme(legend.position = 'bottom',plot.title = element_text(size=14),legend.title = element_text(size=10),axis.title.x = element_text(size=12),axis.title.y = element_text(size=12)) +
  scale_color_manual(values = c("navy", "red"))

plta <- ggarrange(plt1a, plt2a, nrow = 1)
plta
ggsave("/home/yhu2bk/Github/fig/entry_exit_dynamism_professional.png", plta)



# geography where minority businesses enter the most in 2019
uploadpath = "Business_characteristics/Minority_owned/data/distribution/"
entry <-  read_csv(paste0(uploadpath,"va059_bg_mi_20102020_entry_by_minority.csv.xz"))
exit <-  read_csv(paste0(uploadpath,"va059_bg_mi_20102020_exit_by_minority.csv.xz"))
total <-  read_csv(paste0(uploadpath,"va059_bg_mi_20102020_number_business_by_minority.csv.xz"))

all_data <- rbind(entry,exit,total)
temp <- all_data %>%
  filter(measure_type=='count') %>%
  mutate(type=str_remove_all(measure,paste(metrics, collapse = "|")),
         metrics=str_remove_all(measure,paste(type, collapse = "|"))) %>%
  filter(type=='minority_owned_') %>%
  filter(year==2019) %>%
  group_by(geoid,metrics) %>%
  summarise(value=sum(value, na.rm=T)) %>%
  pivot_wider(names_from=metrics, values_from=value) %>%
  mutate(entry_rate=100*new_business/number_business,
         exit_rate=100*exit_business/number_business)

temp_bg2010 <- block_groups("VA", "059", 2010) %>% select(geoid=GEOID, geometry) 
temp_sf <- sf::st_as_sf(merge(temp, temp_bg2010, by.x = c('geoid'), by.y = c('geoid'), all.x = TRUE))

map1 <- ggplot(temp_sf) + 
  geom_sf(aes(fill = number_business)) + 
  scale_y_continuous() + 
  scale_fill_gradient2(low = "blue",
                       mid = "white",
                       high = "red",
                       aesthetics ="fill") +
  labs(fill = "count", title = "Number of Minority-Owned businesses in 2019")

map2 <- ggplot(temp_sf) + 
  geom_sf(aes(fill = entry_rate)) + 
  scale_y_continuous() + 
  scale_fill_gradient2(low = "blue",
                       mid = "white",
                       high = "red",
                       aesthetics ="fill") +
  labs(fill = "entry rate", title = "Entry rate by Minority-Owned businesses in 2019")

map3 <- ggplot(temp_sf) + 
  geom_sf(aes(fill = exit_rate)) + 
  scale_y_continuous() + 
  scale_fill_gradient2(low = "blue",
                       mid = "white",
                       high = "red",
                       aesthetics ="fill") +
  labs(fill = "exit rate", title = "Exit rate by Minority-Owned businesses in 2019")

map <- ggarrange(map1, map2, map3,nrow = 1)
map
ggsave("/home/yhu2bk/Github/fig/map_entry_exit_rate.png", map)



# Job creation and job destruction -------------------------------------------------------
# load the data
uploadpath = "Employment/Minority_owned/data/distribution/"
job_creation <-  read_csv(paste0(uploadpath,"va059_bg_mi_20102020_jobs_creation_by_minority.csv.xz"))
job_destruction <-  read_csv(paste0(uploadpath,"va059_bg_mi_20102019_jobs_destruction_by_minority.csv.xz"))
total <-  read_csv(paste0(uploadpath,"va059_bg_mi_20102020_total_employment_by_minority.csv.xz"))

# all minority-owned businesses
type <- c('minority_owned','non_minority_owned')
metrics <- c('job_creation_new','job_creation_active','business_create_job','total_job_creation','job_destruction_exit','job_destruction_active','business_job_destruction','total_job_destruction','total_employment')

all_data <- rbind(job_creation,job_destruction,total)
temp <- all_data %>%
  filter(measure_type=='count') %>%
  mutate(type=str_remove_all(measure,paste(metrics, collapse = "|")),
         metrics=str_remove_all(measure,paste(type, collapse = "|"))) %>%
  filter(type=='minority_owned_') %>%
  filter(metrics %in% c('job_creation_new','job_creation_active','job_destruction_exit','job_destruction_active','total_employment')) %>%
  filter(year %in% 2011:2020) %>%
  group_by(year,metrics) %>%
  summarise(value=sum(value, na.rm=T)) 

temp01 <- temp %>% filter(metrics %in% c('job_creation_new','job_creation_active')) %>% filter(year %in% 2012:2020) %>% mutate(status=if_else(metrics=='job_creation_new','new','active'))
temp02 <- temp %>% filter(metrics %in% c('job_destruction_exit','job_destruction_active')) %>% mutate(status=if_else(metrics=='job_destruction_exit','exit','active'))

plt1 <- ggplot(temp01, aes(x=factor(year), y=value, fill=status )) +   
  geom_bar(stat="identity",colour="black") +
  ylim(0,7500) +
  scale_fill_manual(values=c("#006DDB", "#DB6D00")) +
  labs(x = "Year", y="jobs created", title='Jobs Creation by Minority-Owned Businesses', fill='') +
  theme(plot.title = element_text(size=14),axis.title.x = element_text(size=12),axis.title.y = element_text(size=12))

plt2 <- ggplot(temp02, aes(x=factor(year), y=value, fill=status )) +   
  geom_bar(stat="identity",colour="black") +
  ylim(0,7500) +
  scale_fill_manual(values=c("#920000","#009999")) +
  labs(x = "Year", y="jobs destroyed", title='Jobs Destruction by Minority-Owned Businesses', fill='') +
  theme(plot.title = element_text(size=14),axis.title.x = element_text(size=12),axis.title.y = element_text(size=12))

plt <- ggarrange(plt1, plt2, nrow = 1)
plt

ggsave("/home/yhu2bk/Github/fig/creation_destruction_dynamism.png", plt)


# employment growth by minority
temp03 <- temp %>% filter(metrics %in% c('total_employment'))
plt3 <- ggplot(temp03, aes(x=factor(year), y=value )) +   
  geom_bar(stat="identity",colour="black") +
  scale_fill_manual(values=c("#006DDB", "#DB6D00")) +
  labs(x = "Year", y="employment", title='Total employement', fill='') +
  theme(plot.title = element_text(size=14),axis.title.x = element_text(size=12),axis.title.y = element_text(size=12))
plt3
ggsave("/home/yhu2bk/Github/fig/employment_minority.png", plt3)




# employment distribution across block groups
temp <- all_data %>%
  filter(measure_type=='count') %>%
  mutate(type=str_remove_all(measure,paste(metrics, collapse = "|")),
         metrics=str_remove_all(measure,paste(type, collapse = "|"))) %>%
  filter(type=='minority_owned_') %>%
  filter(metrics %in% c('total_job_creation','total_job_destruction','total_employment')) %>%
  filter(year==2019) %>%
  dplyr::select(geoid,metrics,value) %>%
  group_by(geoid,metrics) %>%
  summarize(value=mean(value))%>%
  pivot_wider(names_from=metrics, values_from=value) 

temp_bg2010 <- block_groups("VA", "059", 2010) %>% select(geoid=GEOID, geometry) 
temp_sf <- sf::st_as_sf(merge(temp, temp_bg2010, by.x = c('geoid'), by.y = c('geoid'), all.x = TRUE))

map1 <- ggplot(temp_sf) + 
  geom_sf(aes(fill = total_job_creation)) + 
  scale_y_continuous() + 
  scale_fill_gradient2(low = "blue",
                       mid = "white",
                       high = "red",
                       aesthetics ="fill") +
  labs(fill = "count", title = "Jobs Creation by Minority-owned in 2019")

map2 <- ggplot(temp_sf) + 
  geom_sf(aes(fill = total_job_destruction)) + 
  scale_y_continuous() + 
  scale_fill_gradient2(low = "blue",
                       mid = "white",
                       high = "red",
                       aesthetics ="fill") +
  labs(fill = "count", title = "Jobs Destruction by Minority-owned in 2019")

map3 <- ggplot(temp_sf) + 
  geom_sf(aes(fill = total_employment)) + 
  scale_y_continuous() + 
  scale_fill_gradient2(low = "blue",
                       mid = "white",
                       high = "red",
                       aesthetics ="fill") +
  labs(fill = "count", title = "Total Employment in 2019")

map <- ggarrange(map1, map2, map3,nrow = 1)
map
ggsave("/home/yhu2bk/Github/fig/map_creation_destruction.png", map)

