const video = document.getElementById("video");
const overlay = document.getElementById("overlay");
const confidenceLabel = document.getElementById("confidence");
const cameraStatus = document.getElementById("cameraStatus");
const memePanel = document.querySelector(".meme-panel");
const reactionLabel = document.getElementById("reactionLabel");
const confettiLayer = document.getElementById("confettiLayer");
const monkeyImage = document.getElementById("monkeyImage");
const speedFaceImage = document.getElementById("speedFaceImage");
const moggingImage = document.getElementById("moggingImage");

const drawCanvas = document.createElement("canvas");
const drawContext = drawCanvas.getContext("2d");
const overlayContext = overlay.getContext("2d");

let socket;
let latestResult = null;
let frameTimer = null;
let streamReady = false;

async function start() {
  createConfetti();
  await refreshAssetStatus();
  await startCamera();
  connectSocket();
  window.addEventListener("resize", resizeOverlay);
}

async function refreshAssetStatus() {
  const response = await fetch("/api/asset-status");
  const status = await response.json();
  monkeyImage.classList.toggle("available", status.monkeyImageAvailable);
  speedFaceImage.classList.toggle("available", status.speedFaceImageAvailable);
  moggingImage.classList.toggle("available", status.moggingImageAvailable);
}

async function startCamera() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: 960, height: 720, facingMode: "user" },
      audio: false,
    });
    video.srcObject = stream;
    await video.play();
    streamReady = true;
    cameraStatus.textContent = "";
    resizeOverlay();
  } catch (error) {
    cameraStatus.textContent = `Camera unavailable: ${error.message}`;
  }
}

function connectSocket() {
  socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/analyze`);

  socket.addEventListener("open", () => {
    frameTimer = window.setInterval(sendFrame, 160);
  });

  socket.addEventListener("message", (event) => {
    latestResult = JSON.parse(event.data);
    updateUi(latestResult);
  });

  socket.addEventListener("close", () => {
    window.clearInterval(frameTimer);
    frameTimer = null;
    window.setTimeout(connectSocket, 1000);
  });
}

function sendFrame() {
  if (!streamReady || !socket || socket.readyState !== WebSocket.OPEN) {
    return;
  }

  const sourceWidth = video.videoWidth;
  const sourceHeight = video.videoHeight;
  if (!sourceWidth || !sourceHeight) {
    return;
  }

  drawCanvas.width = sourceWidth;
  drawCanvas.height = sourceHeight;
  drawContext.drawImage(video, 0, 0, sourceWidth, sourceHeight);
  socket.send(drawCanvas.toDataURL("image/jpeg", 0.65));
}

function updateUi(result) {
  confidenceLabel.textContent = Number(result.confidence || 0).toFixed(2);
  memePanel.dataset.activeImage = result.activeImage || "";
  document.body.dataset.confetti = result.confettiActive ? "active" : "";
  confettiLayer.style.setProperty("--confetti-intensity", String(Number(result.confettiIntensity || 0).toFixed(2)));
  reactionLabel.textContent = reactionWord(result.activeImage, result.confettiActive);
  monkeyImage.classList.toggle("available", Boolean(result.monkeyImageAvailable));
  speedFaceImage.classList.toggle("available", Boolean(result.speedFaceImageAvailable));
  moggingImage.classList.toggle("available", Boolean(result.moggingImageAvailable));
  drawOverlay(result);
}

function createConfetti() {
  const colors = ["#ff4f81", "#ffd166", "#06d6a0", "#4cc9f0", "#f72585", "#f8f9fa"];
  for (let index = 0; index < 67; index += 1) {
    const piece = document.createElement("span");
    piece.className = "confetti-piece";
    piece.textContent = index % 2 === 0 ? "6" : "7";
    piece.style.setProperty("--x", `${(index * 37) % 100}%`);
    piece.style.setProperty("--delay", `${-((index * 0.137) % 2.4)}s`);
    piece.style.setProperty("--drift", `${((index % 9) - 4) * 9}px`);
    piece.style.setProperty("--spin", `${180 + (index % 7) * 45}deg`);
    piece.style.color = colors[index % colors.length];
    confettiLayer.appendChild(piece);
  }
}

function reactionWord(activeImage, confettiActive) {
  if (activeImage === "speedFace") {
    return "speed";
  }
  if (activeImage === "monkey") {
    return "monkey";
  }
  if (activeImage === "mogging") {
    return "mogging";
  }
  if (confettiActive) {
    return "confetti";
  }
  return "none";
}

function resizeOverlay() {
  const bounds = video.getBoundingClientRect();
  const deviceScale = window.devicePixelRatio || 1;
  overlay.width = Math.round(bounds.width * deviceScale);
  overlay.height = Math.round(bounds.height * deviceScale);
  overlayContext.setTransform(deviceScale, 0, 0, deviceScale, 0, 0);
  if (latestResult) {
    drawOverlay(latestResult);
  }
}

function drawOverlay(result) {
  const bounds = video.getBoundingClientRect();
  overlayContext.clearRect(0, 0, bounds.width, bounds.height);

  const sourceWidth = video.videoWidth;
  const sourceHeight = video.videoHeight;
  if (!sourceWidth || !sourceHeight) {
    return;
  }

  drawBox(result.faceBox, "#43d67d", "Head", sourceWidth, sourceHeight, bounds);
  const handBoxes = result.handBoxes || (result.handBox ? [result.handBox] : []);
  handBoxes.forEach((box, index) => {
    drawBox(box, "#ffcc33", index === 0 ? "Hand" : "Hand", sourceWidth, sourceHeight, bounds);
  });
}

function drawBox(box, color, label, sourceWidth, sourceHeight, bounds) {
  if (!box) {
    return;
  }

  const scale = Math.max(bounds.width / sourceWidth, bounds.height / sourceHeight);
  const renderedWidth = sourceWidth * scale;
  const renderedHeight = sourceHeight * scale;
  const offsetX = (bounds.width - renderedWidth) / 2;
  const offsetY = (bounds.height - renderedHeight) / 2;

  const x = offsetX + box.x * scale;
  const y = offsetY + box.y * scale;
  const size = box.size * scale;

  overlayContext.strokeStyle = color;
  overlayContext.lineWidth = 3;
  overlayContext.strokeRect(x, y, size, size);
  overlayContext.fillStyle = color;
  overlayContext.font = "700 14px system-ui";
  overlayContext.fillText(label, x + 6, Math.max(18, y - 8));
}

start();
