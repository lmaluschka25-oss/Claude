# YOLO model weights

Place your trained detector weights here as `valorant.pt` (or point
`VVC_YOLO_MODEL_PATH` elsewhere). Weights are **not** committed — they are large
and must be trained on footage you are licensed to use.

## Label vocabulary

Train the model to emit these class names (the pipeline interprets them):

| Class            | Meaning                                              |
|------------------|------------------------------------------------------|
| `mm_self`        | The player's own marker on the minimap               |
| `mm_enemy`       | A **revealed** enemy marker on the player's minimap   |
| `mm_enemy:<agent>` | Same, with the agent identified (e.g. `mm_enemy:jett`) |
| `enemy`          | An enemy visible in the 3D viewport (no agent id)    |
| `enemy:<agent>`  | An enemy agent recognized in the viewport            |
| `ally:<agent>`   | An ally visible in the viewport (optional)           |

Only information that is **already visible on the player's screen** belongs in
the training data. Do not label enemies the player could not see — that would
defeat the entire point of this tool and is out of scope.

## Training outline

1. Collect your own recorded VODs (or footage you may legally use).
2. Sample frames (e.g. `ffmpeg -i match.mp4 -vf fps=2 frames/%05d.png`).
3. Annotate with the label vocabulary above (Roboflow, CVAT, Label Studio …).
4. Train with Ultralytics:

   ```bash
   yolo detect train data=valorant.yaml model=yolov8n.pt imgsz=1280 epochs=100
   ```

5. Copy `runs/detect/train/weights/best.pt` to this folder as `valorant.pt`.

## No weights yet?

The app still runs end to end: when weights are missing it automatically falls
back to the deterministic **mock detector**, which produces synthetic but
realistic detections so you can explore the dashboard, the API, and the
analysis. Set `VVC_DETECTOR_BACKEND=mock` to force it explicitly.
