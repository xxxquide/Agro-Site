# Ukraine route map source

The map used in the Geography section is a local inline SVG. It makes no tile, geocoding or map-library request at runtime.

## Boundary source

- Dataset: Natural Earth Vector, Admin 0 Countries, 1:10m
- Repository: https://github.com/nvkelso/natural-earth-vector
- Source commit: ca96624a56bd078437bca8184e78163e5039ad19
- Source file: geojson/ne_10m_admin_0_countries_ukr.geojson
- Source file SHA reported by GitHub: e0ae295012dd7bfb75e0fea1fce5aff554c1a065
- Natural Earth data is public domain. The GeoJSON conversion is also distributed by community mirrors under CC0.

The country feature with ADM0_A3 equal to UKR was extracted, simplified with a Douglas–Peucker tolerance of 0.035 degrees, projected into a 760 × 460 SVG viewBox and stored in templates/ukraine-map.svg.j2.

## Plotted points

- Vinnytsia: 49.2331, 28.4682
- Haisyn: 48.8114, 29.3891
- Port of Odesa: 46.4825, 30.7233
- Kyiv: 50.4501, 30.5234
- CENTRAGRO PLUS demo location: 49.0716, 29.3608

Distances displayed beside the map come from the existing demonstration content. The route is explanatory artwork, not turn-by-turn navigation or a geopolitical boundary statement.
