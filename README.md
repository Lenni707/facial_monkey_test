# Facial Monkey Test

A containerized Python webcam app that shows your camera feed on the left and displays a reaction image on the right:

- `assets/thinking_monkey.jpeg` when your finger is detected near your mouth.
- `assets/speed_face.png` when your eyes are slightly closed, lips are pushed forward, and eyebrows are pushed down.
- `assets/mogger.jpeg` when your index finger is detected along your chin or either side of your jaw.

## Run

```bash
docker compose up --build
```

Open http://localhost:8000 and allow webcam access in the browser.

## Meme Asset

Current reaction image paths:

```text
assets/thinking_monkey.jpeg
assets/speed_face.png
assets/mogger.jpeg
```

Until an active reaction image exists, the app shows a placeholder in the right pane.
