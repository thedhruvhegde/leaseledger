"""Study-area definitions for the multi-city "thousands of futures" simulation.

Every city is a campus-centred bounding box (WGS84 degrees), one or more anchor campuses (the "campus centre" used by
the naive straight-line rule), and the GTFS feeds that serve it. Feed files live in data/multicity/gtfs/ (Ann Arbor
reuses data/raw/gtfs_live/). Provenance of every download is recorded in data/multicity/PROVENANCE.json by
`ledger.multicity.fetch`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ledger.pipeline.feeds import REPO

DATA = REPO / "data" / "multicity"
GTFS_DIR = DATA / "gtfs"
OVERTURE_RELEASE = "2026-11-18.0"


@dataclass(frozen=True)
class Feed:
    key: str            # namespace prefix for ids
    path: Path
    url: str            # where it was downloaded from
    mirror: str         # "MobilityDatabase mdb-latest mirror (GCS)" | "agency S3" | "team member (official URL)"
    route_types: tuple[int, ...] | None = None   # keep only these GTFS route_type values (None = all)


@dataclass(frozen=True)
class Anchor:
    name: str
    lat: float
    lon: float


@dataclass(frozen=True)
class City:
    key: str
    name: str
    campus: str
    bbox: tuple[float, float, float, float]          # (lon_min, lat_min, lon_max, lat_max)
    anchors: tuple[Anchor, ...]
    feeds: tuple[Feed, ...]
    notes: str = ""
    n_futures: int = 1000
    extra: dict = field(default_factory=dict)

    @property
    def lat0(self) -> float:
        return 0.5 * (self.bbox[1] + self.bbox[3])

    @property
    def lon0(self) -> float:
        return 0.5 * (self.bbox[0] + self.bbox[2])

    @property
    def dir(self) -> Path:
        return DATA / self.key


MDB = "https://storage.googleapis.com/storage/v1/b/mdb-latest/o/{}?alt=media"
MIRROR = "MobilityDatabase mdb-latest mirror (storage.googleapis.com)"

CITIES: dict[str, City] = {c.key: c for c in [
    City("annarbor", "Ann Arbor", "University of Michigan",
         (-83.795, 42.225, -83.675, 42.325),
         (Anchor("Central Campus (Diag)", 42.2768, -83.7382), Anchor("North Campus (Pierpont)", 42.2913, -83.7173)),
         (Feed("UM", REPO / "data/raw/gtfs_live/um_gtfs.zip",
               "https://webapps.fo.umich.edu/transit_uploads/google_transit.zip", "team member (official URL)"),
          Feed("AA", REPO / "data/raw/gtfs_live/aaata_gtfs.zip",
               "https://www.theride.org/sites/default/files/google/google_transit.zip", "team member (official URL)")),
         notes="Overture segments reused from data/raw/overture_a2 (same 2026-11-18.0 release)."),
    City("austin", "Austin", "UT Austin",
         (-97.790, 30.240, -97.680, 30.330),
         (Anchor("UT Main Building", 30.2862, -97.7394),),
         (Feed("CM", GTFS_DIR / "austin_capmetro.zip", MDB.format("us-texas-capital-metro-gtfs-150.zip"), MIRROR),)),
    City("uiuc", "Champaign-Urbana", "UIUC",
         (-88.300, 40.070, -88.170, 40.145),
         (Anchor("Main Quad", 40.1076, -88.2272),),
         (Feed("MTD", GTFS_DIR / "uiuc_cumtd.zip",
               MDB.format("us-illinois-champaign-urbana-mass-transit-district-mtd-gtfs-388.zip"), MIRROR),)),
    City("princeton", "Princeton", "Princeton University",
         (-74.720, 40.305, -74.600, 40.385),
         (Anchor("Nassau Hall", 40.3487, -74.6593),),
         (Feed("NJB", GTFS_DIR / "princeton_njt_bus.zip",
               MDB.format("us-new-jersey-new-jersey-transit-nj-transit-gtfs-508.zip"), MIRROR),
          Feed("NJR", GTFS_DIR / "princeton_njt_rail.zip",
               MDB.format("us-new-jersey-new-jersey-transit-nj-transit-gtfs-509.zip"), MIRROR)),
         notes="Princeton TigerTransit has no GTFS feed in the Mobility Database catalog; NJ Transit bus + rail "
               "(incl. the Dinky) only."),
    City("boston", "Cambridge-Boston", "Harvard",
         (-71.150, 42.330, -71.040, 42.400),
         (Anchor("Harvard Yard", 42.3744, -71.1169),),
         (Feed("MBTA", GTFS_DIR / "boston_mbta.zip",
               MDB.format("us-massachusetts-massachusetts-bay-transportation-authority-mbta-gtfs-437.zip"), MIRROR,
               route_types=(0, 1, 3)),),
         notes="MBTA subway, light rail and bus (commuter rail and ferries dropped)."),
    City("nyc", "New York City", "NYU + Columbia",
         (-74.025, 40.680, -73.900, 40.825),
         (Anchor("NYU Washington Sq", 40.7295, -73.9965), Anchor("Columbia Morningside", 40.8075, -73.9626)),
         (Feed("SUB", GTFS_DIR / "nyc_subway.zip", "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip",
               "MTA developer feed (rrgtfsfeeds S3)"),
          Feed("MB", GTFS_DIR / "nyc_manhattan_bus.zip", "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_m.zip",
               "MTA developer feed (rrgtfsfeeds S3)")),
         notes="Subway + Manhattan local bus. Brooklyn/Queens/Bronx bus feeds not included (size); trips into "
               "Brooklyn/Queens parts of the bbox rely on subway + walking."),
    City("sf", "San Francisco", "UCSF + SF State",
         (-122.520, 37.705, -122.355, 37.812),
         (Anchor("UCSF Parnassus", 37.7631, -122.4586), Anchor("SF State", 37.7219, -122.4782)),
         (Feed("MUNI", GTFS_DIR / "sf_muni.zip",
               MDB.format("us-california-san-francisco-municipal-transportation-agency-sfmta-gtfs-2886.zip"), MIRROR),
          Feed("BART", GTFS_DIR / "sf_bart.zip",
               MDB.format("us-california-bay-area-rapid-transit-bart-gtfs-53.zip"), MIRROR))),
]}
