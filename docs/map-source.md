# Ukraine route map source

The map used in the Geography section is a local inline SVG. It makes no tile, geocoding or map-library request at runtime.

## Boundary source

- Dataset: Natural Earth Vector, Admin 1 States and Provinces, 1:10m
- Repository: https://github.com/nvkelso/natural-earth-vector
- Source commit: ca96624a56bd078437bca8184e78163e5039ad19
- Source file: geojson/ne_10m_admin_1_states_provinces.geojson
- Source file SHA reported by GitHub: e0ae295012dd7bfb75e0fea1fce5aff554c1a065
- Natural Earth data is public domain. The GeoJSON conversion is also distributed by community mirrors under CC0.

Features with ISO_A2 equal to UA were extracted, simplified with a Douglas–Peucker
tolerance of 0.045 degrees, projected equirectangularly with the latitude
correction taken at the country's mid-latitude, and stored in
templates/ukraine-map.svg.j2. The viewBox is 760 × 512, proportioned to the
country itself so it fills its card.

Regenerate with `python3 tools/build_map.py --refresh`. The download happens at
build time only; the committed SVG is what the browser receives, so the site
still makes no third-party request.

### Crimea and Sevastopol

Natural Earth's default point of view files the Autonomous Republic of Crimea
and the city of Sevastopol under Russia (`iso_a2: RU`). Ukraine's
internationally recognised borders include both, and the map this replaced drew
them as Ukrainian. `tools/build_map.py` therefore re-adds those two features by
name. This is a deliberate editorial decision recorded here so it is not later
mistaken for a data-cleaning bug and "fixed".

### Oblast subdivisions

The map is drawn as 27 separate region paths rather than one national
silhouette, so Vinnytsia oblast — where the enterprise operates — can be
highlighted, and so the country reads as a country rather than a shape.

## Plotted points

- Vinnytsia: 49.2331, 28.4682
- Haisyn: 48.8114, 29.3891
- Port of Odesa: 46.4825, 30.7233
- Kyiv: 50.4501, 30.5234
- CENTRAGRO PLUS demo location: 49.0716, 29.3608

Distances displayed beside the map come from the existing demonstration content.
All four are now drawn: Kyiv, the port of Odesa, Vinnytsia and Haisyn. Each is a
cubic arc produced by one rule — control points a third and two thirds along the
chord, offset perpendicular by a fixed share of its length — so every route
curves the same way and short hops lift less than long hauls. The routes are
explanatory artwork, not turn-by-turn navigation.
