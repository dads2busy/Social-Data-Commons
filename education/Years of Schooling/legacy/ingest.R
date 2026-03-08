base_dir <- "Years of Schooling/data"
dir.create(paste0(base_dir, "/original/reference_shapes"), FALSE, TRUE)

# get health district associations
districts <- read.csv(paste0(
  "https://raw.githubusercontent.com/uva-bi-sdad/sdc.geographies/main/",
  "VA/State%20Geographies/Health%20Districts/2020/data/distribution/va_ct_to_hd_crosswalk.csv"
))
county_districts <- structure(districts$hd_geoid, names = districts$ct_geoid)

states <- c("DC", "MD", "VA")
years <- 2013:2021

vars <- c(
  "1.m_0" = "B15002_003",
  "2.m_2.5" = "B15002_004",
  "3.m_5.5" = "B15002_005",
  "4.m_7.5" = "B15002_006",
  "5.m_9" = "B15002_007",
  "6.m_10" = "B15002_008",
  "7.m_11" = "B15002_009",
  "8.m_11" = "B15002_010",
  "9.m_12" = "B15002_011",
  "10.m_13" = "B15002_012",
  "11.m_14" = "B15002_013",
  "12.m_14" = "B15002_014",
  "13.m_16" = "B15002_015",
  "14.m_18" = "B15002_016",
  "15.m_19" = "B15002_017",
  "16.m_20" = "B15002_018",
  "1.f_0" = "B15002_020",
  "2.f_2.5" = "B15002_021",
  "3.f_5.5" = "B15002_022",
  "4.f_7.5" = "B15002_023",
  "5.f_9" = "B15002_024",
  "6.f_10" = "B15002_025",
  "7.f_11" = "B15002_026",
  "8.f_11" = "B15002_027",
  "9.f_12" = "B15002_028",
  "10.f_13" = "B15002_029",
  "11.f_14" = "B15002_030",
  "12.f_14" = "B15002_031",
  "13.f_16" = "B15002_032",
  "14.f_18" = "B15002_033",
  "15.f_19" = "B15002_034",
  "16.f_20" = "B15002_035"
)
base_vars <- paste0(
  rep(c("average_years_schooling", "EduGini"), each = 3), c("", "_female", "_male")
)
base_vars[1] <- paste0(base_vars[1], "_rework")
error_vars <- paste0(base_vars, "_error")
sv <- list(
  f = grep("f", names(vars), value = TRUE),
  m = grep("m", names(vars), value = TRUE)
)

# download ACS data, calculate variables, and aggregate
## methods from https://files.eric.ed.gov/fulltext/ED536152.pdf

y <- as.numeric(sub("^.*_", "", sv$f))
Gini <- function(m, p) {
  n <- ncol(p)
  y <- as.numeric(sub("^.*_", "", colnames(p)))
  e <- m^-1 * rowSums(p[, -1] * abs(y[-1] - y[-n]) * p[, -n])
  e[!is.finite(e)] <- 0
  e
}

data <- do.call(rbind, lapply(states, function(state) {
  do.call(rbind, lapply(years, function(year) {
    retrieve <- function(layer) {
      d <- tidycensus::get_acs(
        layer,
        variables = vars,
        year = year,
        state = state,
        output = "wide",
        save = TRUE
      )

      # overall
      d_all <- d[, paste0(sv$f, "E")] + d[, paste0(sv$m, "E")]
      total <- rowSums(d_all)
      total[total == 0] <- 1
      d$average_years_schooling_rework <- (as.matrix(d_all) %*% y) / total
      d$EduGini <- Gini(d$average_years_schooling_rework, d_all / total)
      d_all <- d_all + sqrt(
        (d[, paste0(sv$f, "M")] / 1.645)^2 + (d[, paste0(sv$m, "M")] / 1.645)^2
      ) * 1.645
      d$average_years_schooling_rework_error <- (as.matrix(d_all) %*% y) / total
      d$EduGini_error <- abs(Gini(d$average_years_schooling_rework_error, d_all / total) - d$EduGini)
      d$average_years_schooling_rework_error <- abs(
        d$average_years_schooling_rework_error - d$average_years_schooling_rework
      )

      # female population
      d_female <- d[, paste0(sv$f, "E")]
      total <- rowSums(d_female)
      total[total == 0] <- 1
      d$average_years_schooling_female <- (as.matrix(d_female) %*% y) / total
      d$EduGini_female <- Gini(d$average_years_schooling_female, d_female / total)
      d_female <- d_female + d[, paste0(sv$f, "M")]
      d$average_years_schooling_female_error <- (as.matrix(d_female) %*% y) / total
      d$EduGini_female_error <- abs(Gini(
        d$average_years_schooling_female_error, d_female / total
      ) - d$EduGini_female)
      d$average_years_schooling_female_error <- abs(
        d$average_years_schooling_female_error - d$average_years_schooling_female
      )

      # male population
      d_male <- d[, paste0(sv$m, "E")]
      total <- rowSums(d_male)
      total[total == 0] <- 1
      d$average_years_schooling_male <- (as.matrix(d_male) %*% y) / total
      d$EduGini_male <- Gini(d$average_years_schooling_male, d_male / total)
      d_male <- d_male + d[, paste0(sv$m, "M")]
      d$average_years_schooling_male_error <- (as.matrix(d_male) %*% y) / total
      d$EduGini_male_error <- abs(
        Gini(d$average_years_schooling_male_error, d_male / total) - d$EduGini_male
      )
      d$average_years_schooling_male_error <- abs(
        d$average_years_schooling_male_error - d$average_years_schooling_male
      )

      d <- d[, c("GEOID", base_vars, error_vars)]
      d$year <- year
      n <- nrow(d)
      list(wide = d, tall = list(cbind(
        d[, c("GEOID", "year")],
        measure = rep(base_vars, each = n),
        value = unlist(d[, base_vars], use.names = FALSE),
        moe = unlist(d[, error_vars], use.names = FALSE)
      )))
    }
    counties <- retrieve("county")
    districts <- county_districts[substring(counties$wide$GEOID, 1, 5)]
    districts <- districts[!is.na(districts)]
    do.call(rbind, c(
      retrieve("block group")$tall,
      retrieve("tract")$tall,
      counties$tall,
      if (length(districts)) {
        lapply(
          list(county_districts[substring(counties$wide$GEOID, 1, 5)]),
          function(set) {
            hd_counties <- counties$wide[counties$wide$GEOID %in% names(set), ]
            hd_counties$GEOID <- set[hd_counties$GEOID]
            do.call(rbind, lapply(split(hd_counties, hd_counties$GEOID), function(e) {
              id <- e$GEOID[[1]]
              data.frame(
                GEOID = id,
                measure = base_vars,
                year = year,
                value = colMeans(e[, base_vars]),
                moe = abs(colMeans(e[, base_vars] + e[, error_vars]) - colMeans(e[, base_vars]))
              )
            }))
          }
        )
      }
    ))
  }))
}))
colnames(data) <- tolower(colnames(data))

vroom::vroom_write(data, paste0(base_dir, "/other/acs.csv.xz"), ",")
