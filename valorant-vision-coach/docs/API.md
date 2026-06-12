# API reference

Base URL: `http://localhost:8000/api`. Interactive docs (OpenAPI/Swagger) are at
`http://localhost:8000/docs`.

All times are **seconds into the recording**. `ttl` is the sighting decay window
in seconds. `at` defaults to the end of the match; `ttl` defaults to
`VVC_SIGHTING_TTL_SECONDS`.

## System

| Method & path        | Description                          |
|----------------------|--------------------------------------|
| `GET /health`        | Liveness probe.                      |
| `GET /system/info`   | Backend status (detector/OCR readiness, available maps). |

## Maps

| Method & path        | Description                          |
|----------------------|--------------------------------------|
| `GET /maps`          | List available map names.            |
| `GET /maps/{name}`   | Callouts, sites, and rotation edges. |

## Matches

| Method & path                       | Description                                   |
|-------------------------------------|-----------------------------------------------|
| `GET /matches`                      | List matches (newest first).                  |
| `POST /matches`                     | Upload a recording (multipart). Starts processing. |
| `GET /matches/{id}`                 | Match detail + processing status/progress.    |
| `DELETE /matches/{id}`              | Delete a match, its data, and the stored file.|
| `GET /matches/{id}/rounds`          | Detected rounds.                              |
| `GET /matches/{id}/detections`      | Raw detections. Filters: `start,end,team,source,limit`. |
| `GET /matches/{id}/killfeed`        | Parsed killfeed events.                       |

`POST /matches` fields: `file` (required, video), `map_name` (optional; auto if
omitted).

## Analysis

| Method & path                                  | Query params              |
|------------------------------------------------|---------------------------|
| `GET /matches/{id}/analysis/snapshot`          | `at`, `ttl`               |
| `GET /matches/{id}/analysis/last-known`        | `at`, `ttl`, `include_stale` |
| `GET /matches/{id}/analysis/rotations`         | `at`, `ttl`               |
| `GET /matches/{id}/analysis/site-pressure`     | `at`, `ttl`               |

The **snapshot** endpoint returns all three views in one call — it is what the
dashboard uses as you scrub the timeline.

## Quickstart (curl)

```bash
# Upload a recording (mock backend will synthesize detections)
curl -F "file=@match.mp4" -F "map_name=ascent" http://localhost:8000/api/matches

# Poll status
curl http://localhost:8000/api/matches/1

# Tactical snapshot at 75s with a 15s sighting window
curl "http://localhost:8000/api/matches/1/analysis/snapshot?at=75&ttl=15"
```

## Sample snapshot response

```jsonc
{
  "match_id": 1,
  "map_name": "ascent",
  "at_seconds": 75.0,
  "ttl_seconds": 15.0,
  "last_known": [
    {
      "agent_name": "Jett",
      "map_x": 0.22, "map_y": 0.30, "callout": "A Site",
      "last_seen_seconds": 68.4, "age_seconds": 6.6,
      "confidence": 0.71, "source": "minimap", "stale": false
    }
  ],
  "rotations": [
    {
      "agent_name": "Jett",
      "origin_callout": "A Site",
      "age_seconds": 6.6,
      "candidates": [
        {
          "from_callout": "A Site", "to_callout": "A Link",
          "to_x": 0.30, "to_y": 0.36,
          "distance_norm": 0.16, "eta_seconds": 1.2,
          "likelihood": 0.41, "leads_to_site": null
        }
      ]
    }
  ],
  "site_pressure": [
    {
      "site": "A", "pressure": 0.58, "enemy_count": 1.4,
      "confidence": 0.75, "contributing_callouts": ["A Site", "A Link"]
    },
    { "site": "B", "pressure": 0.0, "enemy_count": 0.0, "confidence": 0.0, "contributing_callouts": [] }
  ]
}
```

## Notes

- `source` is `minimap` (revealed marker, precise location) or `viewport` (seen
  in the 3D view, located by the player's own position as a proxy).
- `likelihood` values within one enemy's `candidates` form a normalized
  distribution.
- All analysis is derived solely from on-screen observations; see
  [ETHICS.md](ETHICS.md).
