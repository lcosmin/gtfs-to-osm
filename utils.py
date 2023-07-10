import json
import logging
import csv
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from inspect import signature


from voluptuous import Schema, Invalid, All, Length, ALLOW_EXTRA
from geopandas import GeoDataFrame
from shapely.geometry import Point


log = logging.getLogger()


non_empty_string = All(str, Length(min=1))

osm_elem_validator = Schema(
    {
        "type": non_empty_string,
        "id": int,
        "lat": float,
        "lon": float,
    },
    required=True,
    extra=ALLOW_EXTRA,
)


def osm_2_gdf(path: str) -> GeoDataFrame:
    """Creates a GeoDataFrame out of the JSON data exported by
    Overpass."""

    with open(path) as f:
        raw_data = json.load(f)

    types: List[str] = []
    points: List[Point] = []
    ids: List[str] = []
    names: List[str] = []

    for elem in raw_data["elements"]:
        # Skip elements which don't pass the validation (they're missing data)
        try:
            osm_elem_validator(elem)
        except Invalid as e:
            log.debug(f"skipping element failing data validation: {e}")
            continue

        # TODO: exclude elements which already have GTFS specific tags

        types.append(elem["type"])
        ids.append(str(elem["id"]))
        points.append(Point(elem["lon"], elem["lat"]))
        names.append(elem.get("tags", {}).get("name", "n/a"))

    return GeoDataFrame(
        {
            "stop_type": types,
            "stop_id": ids,
            "stop_name": names,
        },
        geometry=points,
        crs="EPSG:4326",
    )


def filter_correlated_data(correlation_file: str, gtfs_nodes: GeoDataFrame, osm_nodes: GeoDataFrame) -> Tuple[GeoDataFrame, GeoDataFrame]:
    gtfs_correlated_nodes = set()
    osm_correlated_nodes = set()

    with open(correlation_file) as f:
        reader = csv.reader(f)

        for row in reader:
            # row[0] - gtfs id
            # row[2] - osm id
            gtfs_correlated_nodes.add(row[0])
            osm_correlated_nodes.add(row[2])

    return (gtfs_nodes[~gtfs_nodes["stop_id"].isin(gtfs_correlated_nodes)], 
            osm_nodes[~osm_nodes["stop_id"].isin(osm_correlated_nodes)])


def write_correlation_row(state: "State", file: str):
    row = [
        state.last_clicked_gtfs_element.stop_id,
        state.last_clicked_gtfs_element.stop_name,
        state.last_clicked_osm_element.stop_id,
        state.last_clicked_osm_element.stop_name,
    ]
    log.info(f"writing correlation row {row}")
    with open(file, "a", newline="") as f:
        w = csv.writer(f)

        # row format: gtfs id, gtfs name, osm id, osm name
        w.writerow(row)
        f.flush()


# Some classes to encapsulate specific data; not really needed, but makes working
# with the data easier.


@dataclass
class GtfsStop:
    """GtfsStop contains relevant data about a GTFS bus/tram/etc. stop"""

    stop_id: str
    stop_name: str
    stop_desc: Optional[str]
    stop_lat: float
    stop_lon: float

    @classmethod
    def from_kwargs(cls, **kwargs):
        known_fields = {field for field in signature(cls).parameters}
        # use the native ones to create the class ...
        return cls(**{k: v for k, v in kwargs.items() if k in known_fields})


@dataclass
class OsmStop:
    """OsmStop contains relevant data about an OSM bus/tram/etc. stop"""

    stop_id: field(default_factory=str)  # id is int, but make it string
    stop_name: str

    @classmethod
    def from_kwargs(cls, **kwargs):
        known_fields = {field for field in signature(cls).parameters}
        # use the native ones to create the class ...
        return cls(**{k: v for k, v in kwargs.items() if k in known_fields})


@dataclass
class State:
    last_clicked_gtfs_element: Optional[GtfsStop] = None
    last_clicked_osm_element: Optional[OsmStop] = None

    def reset(self):
        self.last_clicked_gtfs_element = None
        self.last_clicked_osm_element = None

    def both_nodes_set(self) -> bool:
        return (
            self.last_clicked_gtfs_element is not None
            and self.last_clicked_osm_element is not None
        )
