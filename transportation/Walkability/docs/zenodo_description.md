<h3>Overview</h3>
<p>Multi-year Walkability Index derived from LODES employment entropy, GTFS transit proximity, and EPA SLD street connectivity, aggregated from block groups to tracts/counties/health districts. This dataset is produced by the <strong>Social Data Commons</strong> at the University of Virginia as part of the <strong>Walkability Index</strong> data pipeline.</p>
<h3>Provenance</h3>
<p>Derived from the EPA National Walkability Index methodology. Employment entropy (D2A/D2B) computed annually from LEHD LODES + ACS data. Street connectivity (D3B) from EPA SLD V3. Transit proximity (D4C) computed annually from national GTFS feeds. Formula: NatWalkInd = D2A_Ranked/6 + D2B_Ranked/6 + D3B_Ranked/3 + D4C_Ranked/3.</p>
<h3>Coverage</h3><ul>
<li><strong>Temporal coverage:</strong> 2017–2023 (ACS 5-year estimates)</li>
<li><strong>Geographic levels:</strong> County, Health District, Tract</li>
<li><strong>Coverage areas:</strong> National Capital Region (DC metro), Virginia (statewide)</li>
</ul>
<h3>Methodology</h3>
<p>The Walkability Index is a composite measure that ranks block groups according to their relative walkability. It is computed annually (2017-2023) using four components: employment and household land use entropy (D2A/D2B) from LEHD LODES workplace data and ACS household counts, street intersection density (D3B) from the EPA Smart Location Database, and transit proximity (D4C) from GTFS transit stop locations. Block group scores are aggregated to Census tracts, counties, and Health Districts using population-weighted mean (Census 2020 boundaries).</p>
<h3>Source Tables</h3><ul>
<li><a href="https://www.epa.gov/smartgrowth/smart-location-mapping#walkability">Smart Location Database V3, January 2021</a></li>
<li><a href="https://lehd.ces.census.gov/data/lodes/LODES8/">LODES 8 Workplace Area Characteristics</a></li>
<li><a href="https://mobilitydatabase.org">Mobility Database and Transitland GTFS feeds</a></li>
</ul>
<h3>Census Variables</h3><ul>
<li><strong>Custom NatWalkInd = D2A_Ranked/6 + D2B_Ranked/6 + D3B_Ranked/3 + D4C_Ranked/3</strong>: Walkability Index</li>
</ul>
<h3>Measures (2)</h3>
<p><em>Note on naming conventions: Measures containing <code>_geo20</code> are computed using 2020 Census geographic boundaries, while those containing <code>_geo10</code> use 2010 Census geographic boundaries.</em></p>
<dl>
<dt><strong>walkability_index_geo20</strong>: Walkability Index (population-weighted mean)</dt>
<dd>A measure of how walkable a community is, updated annually.</dd>
<dt><strong>walkability_index_geo10</strong>: Walkability Index (population-weighted mean)</dt>
<dd>A measure of how walkable a community is, updated annually.</dd>
</dl>
<h3>Data Sources</h3><ul>
<li><a href="https://www.epa.gov/smartgrowth/smart-location-mapping">Environmental Protection Agency (accessed 2025)</a></li>
<li><a href="https://lehd.ces.census.gov/">Census Bureau LEHD (accessed 2025)</a></li>
<li><a href="https://mobilitydatabase.org">GTFS Transit Feeds (accessed 2025)</a></li>
</ul>
<h3>File Format</h3>
<p>Data files are provided as xz-compressed CSV (<code>.csv.xz</code>) with the following columns: <code>geoid</code>, <code>region_type</code>, <code>region_name</code>, <code>year</code>, <code>measure</code>, <code>value</code>, <code>moe</code> (margin of error, where available). A <code>measure_info.json</code> file provides per-measure metadata.</p>