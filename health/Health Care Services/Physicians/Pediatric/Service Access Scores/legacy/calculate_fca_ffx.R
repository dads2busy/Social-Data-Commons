setwd("./Health Care Services/Physicians/Pediatric/Service Access Scores")

library(tidyverse)
library(catchment)
library(osrm)
library(sf)
library(tidygeocoder)
library(tidycensus)
library(jsonlite)

# peek at vars
#vars <- tidycensus::load_variables("acs5", year = 2021)
# var names for women under 14
vars <- paste0("B01001_0", seq(27, 29))

# providers
provider <- geojsonio::geojson_sf("./data/distribution/ncr_webmd_2022_pediatric_points.geojson") 

## assign IDs just to be explicit
provider$ID <- paste0("l", seq_len(nrow(provider)))
provider <- provider %>% drop_na(geometry)

# population
population <- get_acs(geography = "tract",
                      variables = vars, 
                      state = "va",
                      county = "059",
                      year = 2021, 
                      geometry = TRUE) %>% select(-moe) %>% tidyr::pivot_wider(names_from = "variable", values_from = "estimate") %>% mutate(centroid = st_coordinates(st_centroid(geometry))) %>% rowwise() %>%
  mutate(female_under_14 = sum(c_across(any_of(vars))))

centroid <- population$centroid %>% as.data.frame() %>% cbind(GEOID = population$GEOID)

# traveltime
options(osrm.server = Sys.getenv("OSRM_SERVER"), osrm.profile = "car")

traveltimes <- osrmTable(
  src = centroid[, c("X", "Y")],  #population-demand
  dst = provider[, "geometry"]
  #providers supply
)$duration

population$pediatrician_e2sfca <- catchment_ratio(
  population, provider, traveltimes, 30,
  consumers_value = "female_under_14", providers_id = "ID", providers_value = "doctors", verbose = TRUE
) * 1000

ped_e2sfca <- population %>% select(geoid = GEOID, pediatrician_e2sfca) %>% pivot_longer(cols = pediatrician_e2sfca) %>% st_drop_geometry() %>% mutate(year = 2022, moe = NA) %>% rename(measure = name)

readr::write_csv(ped_e2sfca, xzfile(".data/distribution/va059_webmd_2022_pediatricians_access_scores.csv.xz", compression = 9))

library(scico)

ped_e2sfca_geo <- population %>% select(geoid = GEOID, pediatrician_e2sfca) %>% pivot_longer(cols = pediatrician_e2sfca) %>% mutate(year = 2022, moe = NA) %>% rename(measure = name)

ped_e2sfca_geo %>% 
  # If more than one variable, filter for the name of the variable you want to map
  ggplot() +
  geom_sf(aes(fill = value)) + # fill = name of column with values to map
  labs(fill = "Pediatrician Access Score", # Legend title
       title = "Fairfax County Pediatrician Access", # Graph title
       subtitle = "Enhanced 2-Stage Floating Floating Catchment Areas", 
       caption = "Girls under age 18 and older are Population served \n
       Data Sources: American Community Survey, 5-Year Estimates, \n Age by Sex by Race tables, \n
       WebMD Physician Directory") + 
  #Graph caption
  theme_void() + # Takes out x and y axis, axis labels
  scale_fill_scico(palette = 'lajolla') + # or palette = "vik" (divergent)
  theme(text = element_text(size = 15))

ped_e2sfca_geo %>% 
  # If more than one variable, filter for the name of the variable you want to map
  ggplot() +
  geom_sf(aes(fill = value)) + # fill = name of column with values to map
  labs(fill = "OBGYN Access Score", # Legend title
       title = "Fairfax County OBGYN Access", # Graph title
       subtitle = "Enhanced 2-Stage Floating Floating Catchment Areas", 
       caption = "Women ages 14 and older are Population served \n
       Data Sources: American Community Survey, 5-Year Estimates, \n Age by Sex by Race tables, \n
       Centers for Medicare & Medicaid Services") + 
  #Graph caption
  theme_void() + # Takes out x and y axis, axis labels
  scale_fill_scico(palette = 'lajolla') + # or palette = "vik" (divergent)
  theme(text = element_text(size = 15)) #+
#ylim(-76, -80) +
#xlim(36, 40) +
#geom_sf(data = st_as_sf(provider, coords = c("latitude", "longitude"), crs = 4326))