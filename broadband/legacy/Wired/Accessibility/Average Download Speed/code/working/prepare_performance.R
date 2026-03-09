library("sf")
library("data.table")

url <- "https://ookla-open-data.s3-us-west-2.amazonaws.com/shapefiles/performance/type%3Dfixed/year%3D2020/quarter%3D2/2020-04-01_performance_fixed_tiles.zip"

df <- download.file(url, destfile = "Wired/Accessibility/Average Download Speed/data/original/2020-04-01_performance_fixed_tiles.zip")
