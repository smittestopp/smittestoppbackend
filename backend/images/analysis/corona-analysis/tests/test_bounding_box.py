from corona.map.api import BoundingBox, bounding_box


def test_poi_filtering():
    filtered = bounding_box(54, 12, 1000).contained_elements([
        dict(type='node', is_inside=True, lat=54.001, lon=12.001),
        dict(type='node', is_inside=False, lat=10, lon=10),
        dict(type='node', is_inside=False, lat=58.001, lon=12.001)])
    assert len(filtered) == 1
    assert filtered[0]['is_inside']


def text_boxing():
    box = bounding_box(54, 30, 20)
    assert box.minlat < 54
    assert box.minlon < 30
    assert box.maxlat > 54
    assert box.maxlon > 30


def test_box_contains():
    box = bounding_box(54, 31, 2000)
    point = dict(lat=54.0001, lon=30.9999, type='node')
    assert contains(box, point)
    assert not contains(box, dict(lat=10, lon=10, type='node'))


def contains(box, point):
    return len(box.contained_elements([point])) == 1


def test_combine_boxes():
    box = bounding_box(54, 30, 5).combine(
        bounding_box(52, 31, 5)).combine(
        bounding_box(55, 33, 5))
    assert box.minlat < 52
    assert box.minlon < 30
    assert box.maxlat > 55
    assert box.maxlon > 33


def test_is_inside():
    assert contains(bounding_box(54, 30, 1000),
                    dict(
                        type='node',
                        lat=54.0001,
                        lon=29.9999))
    assert contains(bounding_box(54, 30, 1000),
                    dict(
                        type='way',
                        bounds=dict(
                            minlat=53.9999,
                            minlon=29.9999,
                            maxlat=54.0001,
                            maxlon=30.0001)))
    assert not contains(bounding_box(54, 30, 1000),
        dict(
            type='node',
            lat=10,
            lon=10))
    assert not contains(
        bounding_box(54, 30, 1000),
        dict(
            type='relation',
            bounds=dict(
                minlat=9,
                minlon=9,
                maxlat=11,
                maxlon=11)))
