"""Geography and data: projection, OSM region, sampling, Voronoi zones, CSV."""

import io
import math

import pytest
from shapely.geometry import Point as ShapelyPoint

from src.data import network_from_csv, network_to_csv, sample_network
from src.geo import LocalProjection, load_region
from src.voronoi import assign_customers, service_regions


@pytest.fixture(scope="module")
def city():
    return load_region()


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def test_projection_round_trip_and_accuracy():
    proj = LocalProjection(lat0=22.948, lon0=88.407)
    a, b = (22.9600, 88.4200), (23.0050, 88.4950)  # ~9 km apart inside Kalyani
    xa, ya = proj.to_xy(*a)
    xb, yb = proj.to_xy(*b)
    lat, lon = proj.to_latlon(xb, yb)
    assert math.isclose(lat, b[0], abs_tol=1e-9) and math.isclose(lon, b[1], abs_tol=1e-9)
    flat = math.hypot(xb - xa, yb - ya)
    assert math.isclose(flat, haversine_km(*a, *b), rel_tol=2e-3)  # under 0.2 % at city scale


def test_region_extract_is_sane(city):
    assert 300 < city.area_km2 < 500  # five towns' hull padded by 2.5 km, ~400 km²
    assert len(city.places) >= 400
    assert sum(p["bank"] == 0 for p in city.places) >= 50  # real places on the west bank too
    assert all(city.boundary_xy.contains(ShapelyPoint(p["x"], p["y"])) for p in city.places)


def test_sampling_is_reproducible_and_inside_the_city(city):
    a = sample_network(city, 5, 60, seed=7)
    b = sample_network(city, 5, 60, seed=7)
    assert [p.name for p in a.customers] == [p.name for p in b.customers]
    assert [p.name for p in a.warehouses] == [p.name for p in b.warehouses]
    assert len(a.warehouses) == 5 and len(a.customers) == 60
    hub_osm = {(w.lat, w.lon) for w in a.warehouses}
    assert not any((c.lat, c.lon) in hub_osm for c in a.customers)
    coords = {(round(c.x, 3), round(c.y, 3)) for c in a.customers}
    assert len(coords) == len(a.customers)  # no two customers on the same spot


def test_warehouses_are_spread_out(city):
    net = sample_network(city, 5, 40, seed=3)
    gaps = [math.hypot(a.x - b.x, a.y - b.y) for i, a in enumerate(net.warehouses) for b in net.warehouses[i + 1:]]
    assert min(gaps) > 2.0  # km


@pytest.mark.parametrize("m", [1, 2, 5, 8])
def test_service_regions_partition_the_city(city, m):
    net = sample_network(city, m, 80, seed=5)
    regions = service_regions(net.warehouses, net.region)
    assert set(regions) == {w.id for w in net.warehouses}
    assert math.isclose(sum(r.area for r in regions.values()), net.region.area, rel_tol=1e-6)
    owner = assign_customers(net.customers, net.warehouses)
    for c in net.customers:
        assert regions[owner[c.id]].buffer(1e-6).contains(ShapelyPoint(c.x, c.y))


def test_csv_round_trip(city):
    net = sample_network(city, 4, 30, seed=9)
    back = network_from_csv(io.StringIO(network_to_csv(net)))
    assert len(back.warehouses) == 4 and len(back.customers) == 30
    assert [p.name for p in back.customers] == [p.name for p in net.customers]
    d1 = math.hypot(net.customers[0].x - net.customers[1].x, net.customers[0].y - net.customers[1].y)
    d2 = math.hypot(back.customers[0].x - back.customers[1].x, back.customers[0].y - back.customers[1].y)
    assert math.isclose(d1, d2, rel_tol=1e-3)


def test_csv_rejects_missing_columns():
    with pytest.raises(ValueError):
        network_from_csv(io.StringIO("type,x,y\nwarehouse,1,2\n"))
