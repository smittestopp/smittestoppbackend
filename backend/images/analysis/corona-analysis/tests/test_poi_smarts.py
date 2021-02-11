import pytest

import numpy as np

from corona.map.utils import get_overpass_df_from_list
from corona.map.api import OverpassAPI

pos = dict(
    bislett_stadion=(59.9256534, 10.7320421),
    narvesen_sannergata=(59.9282373, 10.7593426),
    christian_iv_stortorvet=(59.9127317, 10.7454427),
    peppes_jernbanetorget=(59.9113680, 10.7494510),
    kaffebrenneriet_aker_brygge=(59.9111600, 10.7297010)
)

poi = dict(
    ophelia=33730399,
    deli_de_luca_bislett=573358743,
    meny_sannergata=615209026,
    bus_stop_stortorvet=441346630,
    bus_stop_jernbanetorget=4966196395,
    tram_stop_aker_brygge=1365825662
)

types = ['all_buildings', 'amenity_all', 'public_transport', 'offices', 'shop_generalstores']


def test_visit():
    ids = poi_ids(100, types, [
        pos['peppes_jernbanetorget']
    ])

    assert poi['bus_stop_jernbanetorget'] in ids

    assert poi['tram_stop_aker_brygge'] not in ids
    assert poi['deli_de_luca_bislett'] not in ids
    assert poi['meny_sannergata'] not in ids
    assert poi['bus_stop_stortorvet'] not in ids

    assert poi['ophelia'] not in ids


def test_navi():
    ids = poi_ids(100, types, [
        pos['narvesen_sannergata']
    ])

    assert poi['meny_sannergata'] in ids

    assert poi['bus_stop_jernbanetorget'] not in ids
    assert poi['tram_stop_aker_brygge'] not in ids
    assert poi['deli_de_luca_bislett'] not in ids
    assert poi['bus_stop_stortorvet'] not in ids

    assert poi['ophelia'] not in ids


def test_northwards():
    ids = poi_ids(100, types, [
        pos['peppes_jernbanetorget'], pos['narvesen_sannergata']
    ])

    assert poi['bus_stop_jernbanetorget'] in ids
    assert poi['meny_sannergata'] in ids

    assert poi['tram_stop_aker_brygge'] not in ids
    assert poi['deli_de_luca_bislett'] not in ids
    assert poi['bus_stop_stortorvet'] not in ids

    assert poi['ophelia'] not in ids


def test_strandpromenaden():
    ids = poi_ids(100, types, [
        pos['peppes_jernbanetorget'], pos['kaffebrenneriet_aker_brygge']
    ])

    assert poi['bus_stop_jernbanetorget'] in ids
    assert poi['tram_stop_aker_brygge'] in ids

    assert poi['deli_de_luca_bislett'] not in ids
    assert poi['meny_sannergata'] not in ids
    assert poi['bus_stop_stortorvet'] not in ids

    assert poi['ophelia'] not in ids


def test_strandpromenaden_via_stortorget():
    ids = poi_ids(100, types, [
        pos['peppes_jernbanetorget'], pos['christian_iv_stortorvet'], pos['kaffebrenneriet_aker_brygge']
    ])

    assert poi['bus_stop_jernbanetorget'] in ids
    assert poi['tram_stop_aker_brygge'] in ids
    assert poi['bus_stop_stortorvet'] in ids

    assert poi['deli_de_luca_bislett'] not in ids
    assert poi['meny_sannergata'] not in ids

    assert poi['ophelia'] not in ids


def test_parents_visit():
    ids = poi_ids(100, types, [
        pos['peppes_jernbanetorget'],
        pos['bislett_stadion']
    ])

    assert poi['bus_stop_jernbanetorget'] in ids
    assert poi['deli_de_luca_bislett'] in ids

    assert poi['tram_stop_aker_brygge'] not in ids
    assert poi['bus_stop_stortorvet'] not in ids
    assert poi['meny_sannergata'] not in ids

    assert poi['ophelia'] not in ids
    assert poi['ophelia'] not in ids
    assert poi['ophelia'] not in ids
    assert poi['ophelia'] not in ids


def test_full_tour():
    ids = poi_ids(100, types, [
        pos['bislett_stadion'],
        pos['narvesen_sannergata'],
        pos['christian_iv_stortorvet'],
        pos['peppes_jernbanetorget'],
        pos['kaffebrenneriet_aker_brygge']
    ])

    assert poi['bus_stop_jernbanetorget'] in ids
    assert poi['tram_stop_aker_brygge'] in ids

    assert poi['deli_de_luca_bislett'] in ids
    assert poi['meny_sannergata'] in ids
    assert poi['bus_stop_stortorvet'] in ids

    assert poi['ophelia'] not in ids


def test_poi_east_to_west():
    ids = poi_ids(100, types, [
        pos['peppes_jernbanetorget'], pos['kaffebrenneriet_aker_brygge'], pos['bislett_stadion']
    ])

    assert poi['bus_stop_jernbanetorget'] in ids
    assert poi['tram_stop_aker_brygge'] in ids
    assert poi['deli_de_luca_bislett'] in ids

    assert poi['meny_sannergata'] not in ids
    assert poi['bus_stop_stortorvet'] not in ids

    assert poi['ophelia'] not in ids


def poi_ids(d, query_types, traj):
    raw = OverpassAPI().query_points_batched(traj, query_types, distances=d)
    results = np.array_split(raw, len(traj))
    pois_list = []
    for result in results:
        points_of_interest = get_overpass_df_from_list(result)
        if points_of_interest is not None:
            pois_list = pois_list + list(points_of_interest.id)
    return pois_list
