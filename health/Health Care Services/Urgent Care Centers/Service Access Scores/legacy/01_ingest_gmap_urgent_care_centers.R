library(googleway)
library(data.table)

format_res <- function(res) {
  setNames(
    cbind(
      googleway::access_result(res, "coordinates"),
      googleway::access_result(res, "place_name"),
      googleway::access_result(res, "place"),
      res$results$rating 
    )
    , c("lat", "long", "name", "place_id", "rating")
  )
}

do_search <- function(search_string, key, location, radius, page_token = NULL) {
  
  google_places(
    search_string = search_string,
    location = location,
    key = key,
    radius = radius,
    page_token = page_token
  )
}

full_search <- function(search_string, key, location, radius) {
  
  counter <- 0
  
  page_token <- NULL ## can start on NULL because it means we're doing the first query
  is_another_page <- TRUE 
  
  ## initialize a data.frame to store the results
  df <- data.frame(
    lat = vector("numeric", 0L)
    , long = vector("numeric", 0L)
    , name = vector("character", 0L)
    , place_id = vector("character", 0L)
  )
  
  while( is_another_page ) {
    
    res <- do_search(search_string, key, location, radius, page_token)
    
    if( res$status == "OK" ) { ## check a valid result was returned
      
      if( counter == 0 ) {
        df <- format_res( res )
      } else {
        df <- rbind(df, format_res( res ) )
      }
      
      counter <- counter + 1
    } else {
      ## print a message for not-OK results
      print(paste0(res[["status"]], " for ", paste0(location, collapse = ", ") ))
    }
    
    page_token <- res[["next_page_token"]]
    is_another_page <- !is.null( page_token )
    Sys.sleep(3)  ## Sleep the function before the next call because there's a time limit
  }
  return(df)
}


nrc_gmap_coords <- data.table::fread("Health Care Services/nrc_gmap_coords.csv")
# nrc_gmap_coords <- data.table::fread("Health Care Services/nrc_gmap_coords_15k_m.csv")

if(exists("result_all")) rm("result_all")
for (i in 9:224) {
  print(i)
  
  result <- data.table::setDT(
    full_search(
      search_string = 'urgent care center',
      key = Sys.getenv("GOOGLE_API_KEY"),
      location = c(nrc_gmap_coords$lat[i], nrc_gmap_coords$long[i]),
      radius = 5000
    )
  )
  
  if (exists("result_all")) {
    result_all <- unique(data.table::rbindlist(list(result_all, result[result$rating > 0,])))
  } else {
    result_all <- result[result$rating > 0,]
  }
  
  data.table::fwrite(result_all, paste0("Health Care Services/Urgent Care Centers/Service Access Scores/data/working/result_all_15k_", i, ".csv"))
}


# 350, 504 - restarted at 351, need to combine

res1 <- fread("Health Care Services/Urgent Care Centers/Service Access Scores/data/working/result_all_350.csv")
res2 <- fread("Health Care Services/Urgent Care Centers/Service Access Scores/data/working/result_all_504.csv")
res_fnl <- rbindlist(list(res1, res2))

fwrite(res_fnl, "Health Care Services/Urgent Care Centers/Service Access Scores/data/working/ncr_pt_gmap_2022_urgent_care_centers_10k.csv")


# res_15k_fnl <- fread("Health Care Services/Urgent Care Centers/Service Access Scores/data/working/result_all_15k_224.csv")




