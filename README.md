# Facial Monkey Test

A containerized Python webcam app that shows your camera feed on the left and displays a reaction image on the right:

- `assets/thinking_monkey.jpeg` when your finger is detected near your mouth.
- `assets/speed_face.png` when your eyes are closed and your lips are closed in a small oval shape.
- `assets/mogger.jpeg` when your index finger is detected on your lower chin, away from the mouth.

The right pane also shows one word for the current reaction: `none`, `monkey`, `speed`, or `mogging`.

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
