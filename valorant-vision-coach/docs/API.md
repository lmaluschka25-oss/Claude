# API reference

Base URL: `http://localhost:8000/api`. Interactive docs at `/docs`.

A **match** owns many **rounds**; each round is one uploaded recording.
Match-level **intelligence** is aggregated across the match's rounds.

## System & maps

| Method & path        | Description                          |
|----------------------|--------------------------------------|
| `GET /health`        | Liveness probe.                      |
| `GET /system/info`   | Detector/OCR status, available maps. |
| `GET /maps`          | List map names.                      |
| `GET /maps/{name}`   | Callouts, sites, rotation edges.     |

## Matches

| Method & path                     | Description                                   |
|-----------------------------------|-----------------------------------------------|
| `GET /matches`                    | List matches (with round counts).             |
| `POST /matches`                   | Create a match. Body: `{name?, map_name?, side?}`. |
| `GET /matches/{id}`               | Match detail + its rounds.                    |
| `DELETE /matches/{id}`            | Delete match, rounds, and files.              |
| `GET /matches/{id}/rounds`        | List the match's rounds.                      |
| `POST /matches/{id}/rounds`       | Upload a recording (multipart `file`, optional `map_name`). Starts processing. |
| `GET /matches/{id}/intelligence`  | Full dashboard payload. Optional `?round_id=` to focus a round's scene. |

## Rounds

| Method & path                          | Description                          |
|----------------------------------------|--------------------------------------|
| `GET /rounds/{id}`                     | Round status/metadata.               |
| `DELETE /rounds/{id}`                  | Delete a round.                      |
| `GET /rounds/{id}/detections`          | Raw detections for the round.        |
| `GET /rounds/{id}/video`              | Stream the recording (HTTP range).   |
| `GET /rounds/{id}/minimap-preview`     | PNG calibration frame. Params: `t`, `mask`, `x_frac,y_frac,w_frac,h_frac`, `sat_min,val_min`. |

## The intelligence payload

`GET /matches/{id}/intelligence` returns everything the dashboard renders:

```jsonc
{
  "match": { "id": 1, "name": "...", "map_name": "ascent", "side": "attack",
             "rounds_count": 3, "completed_rounds": 3 },
  "current_round": { "round_number": 3, "status": "completed", ... },
  "detected_info": { "map_name": "ascent", "side": "attack", "score_text": "4-2",
                     "round_time": "1:12", "players_alive_ally": 5,
                     "players_alive_enemy": 5, "economy": "Full Buy" },
  "minimap_markers": [ { "team": "enemy", "agent_name": "Killjoy",
                         "map_x": 0.8, "map_y": 0.24, "callout": "B Site",
                         "dead": false, "kind": "player" } ],
  "utilities": [ { "kind": "smoke", "agent_name": "Omen", "callout": "A Site" } ],
  "timeline": [ { "timestamp_seconds": 6.2, "kind": "spotted", "label": "Enemy Seen" } ],
  "detected_positions": [ { "agent_name": "Jett", "callout": "A Main", "age_seconds": 2.1 } ],
  "position_probabilities": [ { "site": "A", "probability": 0.59 },
                              { "site": "B", "probability": 0.41 } ],
  "patterns": [ { "kind": "anchor", "text": "Killjoy anchors B",
                  "detail": "3/3 rounds", "confidence": 0.95 } ],
  "heatmap": [ { "x": 0.8, "y": 0.24, "weight": 1.0 } ],
  "match_memory": { "rounds_analyzed": 3, "site_presence": {"A":0.67,"B":0.33,"MID":0},
                    "common_utility": "Smoke", "enemy_economy": "Full Buy",
                    "confidence": 0.56 },
  "enemy_profiles": [ { "agent_name": "Killjoy", "favored_site": "B",
                        "site_share": 1.0, "rotation_tendency": "Rarely rotates",
                        "rounds_seen": 3 } ],
  "weapon_economy": { "enemy_label": "Full Buy", "enemy_tier": "full",
                      "ally_label": "Full Buy", "ally_tier": "full" },
  "recommendation": { "best_site": "B", "success_probability": 0.8,
                      "confidence": 0.56, "confidence_label": "Medium",
                      "reasons": ["Enemies commit to A most ...", "..."],
                      "suggested_play": ["Take B with 3–4 players.", "..."] },
  "analysis_log": [ { "step": 1, "title": "Map Identified", "detail": "ascent (99%)" } ]
}
```

## Quickstart (curl)

```bash
M=$(curl -s -X POST localhost:8000/api/matches -H 'Content-Type: application/json' \
     -d '{"map_name":"ascent","side":"attack"}' | jq .id)
curl -s -F "file=@round1.mp4" localhost:8000/api/matches/$M/rounds
curl -s "localhost:8000/api/matches/$M/intelligence" | jq .recommendation
```

All values are derived from on-screen observations aggregated across rounds —
never hidden state. See [ETHICS.md](ETHICS.md).
