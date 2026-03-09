# Broadbandnow extraction tools


## General description of the scripts

1. `bbn_filler.py`
      - `retrieve_address_from_fips.py`
            - Given a fips code (any length), return a data frame containing the address.
      - `bbn.py`
            - Given the address returned from the above module, produce a data frame after querying broadbandnow. (Can replace an empty data frame).
      - The strategy is to randomly select a point in the shapefiles, then reverse-geocode to retrieve the address to query broadbandnow data. If no hit is returned, we double the number of points queried and repeat until at least one hit is returned
            - We use this strategy because not every address corresponds to a hit on broadbandnow
            - We also use this strategy so we can minimize the number of queries necessary to accomplish the task