from app.vision.maps import list_maps, load_map


def test_maps_available():
    assert "ascent" in list_maps()


def test_load_map_structure():
    game_map = load_map("ascent")
    assert game_map is not None
    assert game_map.display_name == "Ascent"
    assert "A" in game_map.sites and "B" in game_map.sites
    # Every edge endpoint must reference a real callout.
    for cid, neighbours in game_map.adjacency.items():
        assert cid in game_map.callouts
        for n in neighbours:
            assert n in game_map.callouts


def test_nearest_callout():
    game_map = load_map("ascent")
    nearest = game_map.nearest_callout(0.80, 0.24)
    assert nearest is not None and nearest.id == "b_site"


def test_reachable_is_bounded_and_grows():
    game_map = load_map("ascent")
    near = game_map.reachable("a_main", 0.1)
    far = game_map.reachable("a_main", 1.5)
    assert "a_main" in near
    assert len(far) >= len(near)
    # Nothing exceeds the distance bound.
    assert all(d <= 0.1 + 1e-9 for d in near.values())


def test_site_centroid_matches_plot():
    game_map = load_map("ascent")
    cx, cy = game_map.site_centroid("A")
    assert abs(cx - 0.20) < 1e-6 and abs(cy - 0.22) < 1e-6
