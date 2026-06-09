# PLAN

## Completed
- Created the project plan for a containerized Python browser app.
- Chose a browser-based webcam flow so Docker does not need direct camera access.
- Added the FastAPI/WebSocket backend.
- Added the browser webcam UI with left camera pane, right meme pane, detection boxes, and confidence display.
- Added the `assets/` folder and switched the meme display to `assets/thinking_monkey.jpeg`.
- Added Dockerfile and Docker Compose configuration.
- Verified `docker compose build` succeeds after Docker was started.
- Started the app container with `docker compose up -d`.
- Initialized the local git repository.
- Created and pushed the public GitHub repository: https://github.com/Lenni707/facial_monkey_test

## In Progress
- None.

## Future
- Replace `assets/thinking_monkey.jpeg` if a different meme image is wanted later.
- Open the app in a browser and verify webcam permissions.
- Tune the finger-to-mouth confidence threshold if needed.
