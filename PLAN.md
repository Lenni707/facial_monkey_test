# PLAN

## Completed
- Created the project plan for a containerized Python browser app.
- Chose a browser-based webcam flow so Docker does not need direct camera access.
- Added the FastAPI/WebSocket backend.
- Added the browser webcam UI with left camera pane, right meme pane, detection boxes, and confidence display.
- Added the `assets/` folder with `assets/monkey_thinking.png` reserved for the user-supplied meme.
- Added Dockerfile and Docker Compose configuration.
- Initialized the local git repository.
- Created and pushed the public GitHub repository: https://github.com/Lenni707/facial_monkey_test

## In Progress
- None.

## Future
- Add `assets/monkey_thinking.png` manually.
- Start Docker Desktop or the Docker daemon, then rerun `docker compose build`.
- Run the app with Docker and verify webcam permissions in the browser.
- Tune the finger-to-mouth confidence threshold if needed.
