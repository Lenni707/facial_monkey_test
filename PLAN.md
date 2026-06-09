# PLAN

## Completed
- Created the project plan for a containerized Python browser app.
- Chose a browser-based webcam flow so Docker does not need direct camera access.
- Added the FastAPI/WebSocket backend.
- Added the browser webcam UI with left camera pane, right meme pane, detection boxes, and confidence display.
- Added the `assets/` folder and switched the meme display to `assets/thinking_monkey.jpeg`.
- Added a second facial-expression trigger for `assets/speed_face.png`.
- Added `assets/speed_face.png`.
- Lowered the speed-face threshold to `0.57`.
- Changed the speed-face criteria to closed eyes plus oval/circle mouth shape.
- Added a chin/jaw index-finger trigger for `assets/mogger.jpeg`.
- Added Dockerfile and Docker Compose configuration.
- Verified `docker compose build` succeeds after Docker was started.
- Started the app container with `docker compose up -d`.
- Initialized the local git repository.
- Created and pushed the public GitHub repository: https://github.com/Lenni707/facial_monkey_test

## In Progress
- None.

## Future
- Replace `assets/thinking_monkey.jpeg` if a different meme image is wanted later.
- Replace `assets/speed_face.png` if a different expression image is wanted later.
- Add or replace `assets/mogger.jpeg` for the chin/jaw gesture.
- Open the app in a browser and verify webcam permissions.
- Tune the finger-to-mouth confidence threshold if needed.
- Tune the facial-expression confidence threshold if needed.
- Tune the chin/jaw gesture confidence threshold if needed.
