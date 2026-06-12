"""Map metadata endpoints (callouts + rotation graph for the dashboard)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...schemas import CalloutOut, MapMeta
from ...vision.maps import list_maps, load_map

router = APIRouter(prefix="/maps", tags=["maps"])


@router.get("", response_model=list[str])
def available_maps() -> list[str]:
    return list_maps()


@router.get("/{name}", response_model=MapMeta)
def get_map(name: str) -> MapMeta:
    game_map = load_map(name)
    if game_map is None:
        raise HTTPException(status_code=404, detail=f"Unknown map: {name}")
    return MapMeta(
        name=game_map.name,
        display_name=game_map.display_name,
        image=game_map.image,
        sites=game_map.sites,
        callouts=[
            CalloutOut(id=c.id, name=c.name, x=c.x, y=c.y, site=c.site)
            for c in game_map.callouts.values()
        ],
        edges=[[a, b] for a, neighbours in game_map.adjacency.items() for b in neighbours if a < b],
    )
