library(data.table)
library(jsonlite)
library(zipcodeR)
library(readr)

# Medicare Physician & Other Practitioners - by Provider
cms_versions <- c(
  "2021"="5a6f0f6f-0439-403d-bd99-2c7631003cb1",
  "2020"="dc1b6500-91b9-4bc9-98ed-8b810c727e66",
  "2019"="a399e5c1-1cd1-4cbe-957f-d2cc8fe5d897",
  "2018"="a5cfcc24-eaf7-472c-8831-7f396c77a890",
  "2017"="bed1a455-2dad-4359-9cec-ec59cf251a14",
  "2016"="9301285e-f2ff-4035-9b59-48eaa09a0572",
  "2015"="acba6dc6-3e76-4176-9564-84ab5ea4c8aa",
  "2014"="d3d74823-9909-4177-946d-cdaa268b90ab",
  "2013"="bbec6d8a-3b0d-49bb-98be-3170639d3ab5"
)

# Primary care doctor types
prim_docs <- c("Internal%20Medicine","Pediatric%20Medicine","Family%20Practice","Obstetrics%20%26%20Gynecology")

# Virginia zip codes
va_zips <- zipcodeR::search_state("VA")[, c("zipcode")][[1]]
va_zips_arl <- zipcodeR::search_state("VA")
va_zips_arl <- va_zips_arl[va_zips_arl$county=="Arlington County", c("zipcode")][[1]]

# Get CMS Data
for (z in va_zips_arl) {
  for (y in names(cms_versions[1])) {
    for (d in prim_docs) {
      dataset <- cms_versions[[y]]
      url <- paste0("https://data.cms.gov/data-api/v1/dataset/",
                    dataset,
                    "/data?filter[Rndrng_Prvdr_Zip5]=",
                    z,
                    "&filter[Rndrng_Prvdr_Type]=",
                    d)
      print(url)
      data <- fromJSON(url)
      fwrite(data, paste0("Access to Care (HOI)/data/working/va_docs_",
                          d,
                          "_",
                          y,
                          "_",
                          z,
                          ".csv"))
      Sys.sleep(5)
    }
  }
}




