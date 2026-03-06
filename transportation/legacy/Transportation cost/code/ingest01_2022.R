
#Code for getting Transportation data from H+T index. Create an account with H+T index to access the data. 

#The following link is for Virginia data by Census tracts
#H+T index link "https://htaindex.cnt.org/"

#First step is getting the URL of the file
URL <- "https://htaindex.cnt.org/download/download.php?data_yr=2019&focus=tract&geoid=51"

#Set the File destination on your system
destination <- "~/output.csv"

#downloading the file with R
download.file(URL,destination)
