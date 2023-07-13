import json
import logging
import csv
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
from inspect import signature
from enum import Enum


from voluptuous import (
    Schema,
    Invalid,
    All,
    Any,
    Optional as Opt,
    Required,
    Length,
    ALLOW_EXTRA,
)
from geopandas import GeoDataFrame
from shapely.geometry import Point


log = logging.getLogger()


class ElemType(Enum):
    NODE = "node"
    WAY = "way"
    WAY_NODE = "way_node"


non_empty_string = All(str, Length(min=1))


# Validates regular "bus stop" nodes
osm_node_stop_validator = Schema(
    {
        "type": "node",
        "id": int,
        "lat": float,
        "lon": float,
        "tags": All(
             Schema({Opt("name"): non_empty_string}, extra=ALLOW_EXTRA),
             # make sure at least one of the expected values is there
             Schema(
                 Required(
                    Any(
                        Schema({"public_transport": "platform"}, extra=ALLOW_EXTRA),
                        Schema({"highway": "bus_stop"}, extra=ALLOW_EXTRA),
                    )
                ), 
                extra=ALLOW_EXTRA
            ),
        ),
        # TODO
    },
    required=True,
    extra=ALLOW_EXTRA,
)

osm_way_stop_validator = Schema(
    {
        "type": "way",
        "id": int,
        "nodes": All([int], Length(min=2)),
        "tags": {"public_transport": "platform"},
    },
    extra=ALLOW_EXTRA,
    required=True,
)

osm_node_part_of_way_validator = Schema(
    {
        "type": "node",
        "id": int,
        "lat": float,
        "lon": float,
    },
    required=True,
)

validators = {
    ElemType.NODE: osm_node_stop_validator,
    ElemType.WAY: osm_way_stop_validator,
    ElemType.WAY_NODE: osm_node_part_of_way_validator,
}


def _is_elem_type(elem_type: ElemType, elem: dict, quiet: bool = False) -> bool:
    """Validates `elem` with the data validator for `elem_type` to see if it
    matches."""
    try:
        validators[elem_type](elem)
        return True
    except Exception as e:
        if not quiet:
            log.error(f"failed to validate element type '{elem_type}', data {elem}: {e}")
        return False


def osm_2_gdf(path: str) -> GeoDataFrame:
    """Creates a GeoDataFrame out of the JSON data exported by
    Overpass."""

    with open(path) as f:
        raw_data = json.load(f)

    types: List[str] = []
    points: List[Point] = []
    ids: List[str] = []
    names: List[str] = []

    platforms: List[dict] = []
    platform_nodes: Dict[str, dict] = {}

    for elem in raw_data["elements"]:
        # Data should contain:
        # 1) regular nodes (type: node, id, lat, lon, tags.name, tags.public_transport=platform)
        # 2) platforms (type: way, id, nodes, tags.name, tags.public_transport=platform)
        # 3) platform nodes (type: node, only id, lat and lon)

        # A regular node - can be standalone or part of a way. Standalone nodes have tags,
        # way nodes usually don't, so try to validate the data as a standalone node first.
        if elem["type"] == ElemType.NODE.value:

            if _is_elem_type(ElemType.NODE, elem, quiet=True):
                types.append(elem["type"])
                ids.append(str(elem["id"]))
                points.append(Point(elem["lon"], elem["lat"]))
                names.append(elem.get("tags", {}).get("name", "n/a"))
                continue

            if _is_elem_type(ElemType.WAY_NODE, elem):
                platform_nodes[str(elem["id"])] = {
                    # "type": "node",        # not needed
                    # "id": str(elem["id"]),
                    "point": Point(elem["lon"], elem["lat"]),
                }
                continue

        elif elem["type"] == ElemType.WAY.value:

            # platform (way)
            if _is_elem_type(ElemType.WAY, elem):
                # For platforms, we'll represent on the map only the first node
                # But the coordinates of the node to draw will be known after the
                # whole data file has been parsed. So, in the mean while, save the
                # data
                platforms.append(
                    {
                        "type": "way",
                        "id": str(elem["id"]),
                        "name": elem.get("tags", {}).get("name", "n/a"),
                        "nodes": elem["nodes"],
                    }
                )
                continue


        # TODO: exclude elements which already have GTFS specific tags

    log.info(f"resolving nodes of {len(platforms)} platforms")

    try:
        for platform in platforms:
            # get the first node of the way which has the needed data
            for node in platform["nodes"]:
                try:
                    n = platform_nodes[str(node)]
                except KeyError as e:
                    log.error(f"platform node {node} not found in data")
                    continue
                else:
                    types.append(platform["type"])
                    ids.append(platform["id"])
                    points.append(n["point"])
                    names.append(platform["name"])
                    break
            else:
                log.error(f"failed to find a node for platform {platform}")
    except Exception as e:
        log.exception(f"fooock: {e}")

    return GeoDataFrame(
        {
            "stop_type": types,
            "stop_id": ids,
            "stop_name": names,
        },
        geometry=points,
        crs="EPSG:4326",
    )


def filter_correlated_data(
    correlation_file: str, gtfs_nodes: GeoDataFrame, osm_nodes: GeoDataFrame
) -> Tuple[GeoDataFrame, GeoDataFrame]:
    gtfs_correlated_nodes = set()
    osm_correlated_nodes = set()

    with open(correlation_file) as f:
        reader = csv.reader(f)

        for row in reader:
            # row[0] - gtfs id
            # row[2] - osm id
            gtfs_correlated_nodes.add(row[0])
            osm_correlated_nodes.add(row[2])

    return (
        gtfs_nodes[~gtfs_nodes["stop_id"].isin(gtfs_correlated_nodes)],
        osm_nodes[~osm_nodes["stop_id"].isin(osm_correlated_nodes)],
    )


def write_correlation_row(state: "State", file: str):
    row = [
        state.last_clicked_gtfs_element.stop_id,
        state.last_clicked_gtfs_element.stop_name,
        state.last_clicked_osm_element.stop_type,
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

    stop_type: str 
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


if __name__ == "__main__":
    
    logging.basicConfig(level=logging.DEBUG)
    osm_2_gdf("data/bucuresti.json")
