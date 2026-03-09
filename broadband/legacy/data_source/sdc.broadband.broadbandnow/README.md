# sdc.broadband.broadbandnow

Tools to access and prepare data scrapped from broadbandnow.com

## Graph
```mermaid
graph LR;
           query_year=2023-->Broadbandnow;
           Broadbandnow-->speed;
           Broadbandnow-->down_up;
           Broadbandnow-->price;
           Broadbandnow-->name;
           Broadbandnow-->type;
           Broadbandnow-->address;
```

## Example data
```python
df = pd.read_csv('13121.csv.xz', dtype={'GEOID20':object})
df
           speed   down_up   price                       name           type                                            address  year_parsed       GEOID20   latitude  longitude
0      5000 Mbps  Download  180.00                 AT&T Fiber  Internet 5000  Milton, Fulton County, Georgia, 30005, United ...         2023  131210116432  34.100587 -84.256308
1      5000 Mbps    Upload  180.00                 AT&T Fiber  Internet 5000  Milton, Fulton County, Georgia, 30005, United ...         2023  131210116432  34.100587 -84.256308
2      1200 Mbps  Download   80.00                    Xfinity  Gigabit Extra  Milton, Fulton County, Georgia, 30005, United ...         2023  131210116432  34.100587 -84.256308
3        35 Mbps    Upload   80.00                    Xfinity  Gigabit Extra  Milton, Fulton County, Georgia, 30005, United ...         2023  131210116432  34.100587 -84.256308
4       940 Mbps  Download   70.00  CenturyLink Fiber Gigabit            NaN  Milton, Fulton County, Georgia, 30005, United ...         2023  131210116432  34.100587 -84.256308
...          ...       ...     ...                        ...            ...                                                ...          ...           ...        ...        ...
80906     3 Mbps    Upload  109.99                  HughesNet  Internet Only  1094, Amsterdam Avenue Northeast, North Highla...         2023  131210001001  33.787953 -84.351274
80907    25 Mbps  Download  139.99                  HughesNet  Internet Only  1094, Amsterdam Avenue Northeast, North Highla...         2023  131210001001  33.787953 -84.351274
80908     3 Mbps    Upload  139.99                  HughesNet  Internet Only  1094, Amsterdam Avenue Northeast, North Highla...         2023  131210001001  33.787953 -84.351274
80909    25 Mbps  Download  159.99                  HughesNet  Internet Only  1094, Amsterdam Avenue Northeast, North Highla...         2023  131210001001  33.787953 -84.351274
80910     3 Mbps    Upload  159.99                  HughesNet  Internet Only  1094, Amsterdam Avenue Northeast, North Highla...         2023  131210001001  33.787953 -84.351274

[80911 rows x 10 columns]
```
