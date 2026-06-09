# Facial Monkey Test

A containerized Python webcam app that shows your camera feed on the left and displays `assets/thinking_monkey.jpeg` on the right when your finger is detected near your mouth.

## Run

```bash
docker compose up --build
```

Open http://localhost:8000 and allow webcam access in the browser.

## Meme Asset

Add your image here:

```text
assets/thinking_monkey.jpeg
```

Until that file exists, the app shows a placeholder in the right pane.
