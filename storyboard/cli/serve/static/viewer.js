// State management
const state = {
  scenes: [],
  currentScene: null,
  currentFrameIndex: 0,
  isFirstRender: true,
};

async function init() {
  const path = window.location.pathname;

  if (path === "/" || path === "/index.html") {
    await loadSceneList();
    renderHome();
  } else if (path.startsWith("/scene/")) {
    const sceneId = path.split("/scene/")[1];
    await loadSceneList();
    await loadScene(sceneId);
    renderSceneViewer();
  }

  // Setup keyboard navigation
  window.addEventListener("keydown", (e) => {
    if (state.currentScene) {
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        navigateFrame(-1);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        navigateFrame(1);
      }
    }
  });
}

// Load scene list from API
async function loadSceneList() {
  try {
    const response = await fetch("/api/metadata");
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || "Failed to load metadata");
    }
    const data = await response.json();
    state.scenes = data.scenes || [];
  } catch (error) {
    alert(`Error loading scenes: ${error.message}`);
    console.error(error);
  }
}

// Load specific scene
async function loadScene(sceneId) {
  try {
    const response = await fetch(`/api/scene/${sceneId}`);
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || "Failed to load scene");
    }
    state.currentScene = await response.json();
    state.currentFrameIndex = 0;
  } catch (error) {
    alert(`Error loading scene: ${error.message}`);
    console.error(error);
  }
}

// Render home page (scene list)
function renderHome() {
  const app = document.getElementById("app");

  let html = `
        <div class="container">
            <h1>Storyboard Scenes</h1>
            <div class="scene-grid">
    `;

  for (const scene of state.scenes) {
    // Get preview image (first frame) - we'll need to fetch scene metadata
    html += `
            <div class="scene-card" onclick="navigateToScene('${
              scene.scene_id
            }')">
                <div class="scene-preview" data-scene-id="${scene.scene_id}">
                    <div class="loading">Loading...</div>
                </div>
                <div class="scene-info">
                    <h3>${scene.scene_name}</h3>
                    <p>${scene.frame_count} frame${
      scene.frame_count !== 1 ? "s" : ""
    }</p>
                </div>
            </div>
        `;
  }

  html += `
            </div>
        </div>
    `;

  app.innerHTML = html;

  // Load preview images
  loadPreviewImages();
}

// Load preview images for scene cards
async function loadPreviewImages() {
  for (const scene of state.scenes) {
    try {
      const response = await fetch(`/api/scene/${scene.scene_id}`);
      if (response.ok) {
        const sceneData = await response.json();
        if (sceneData.frames && sceneData.frames.length > 0) {
          const firstFrame = sceneData.frames[0];
          if (firstFrame.assets && firstFrame.assets.image) {
            const previewDiv = document.querySelector(
              `.scene-preview[data-scene-id="${scene.scene_id}"]`
            );
            if (previewDiv) {
              const imgPath = encodeURIComponent(firstFrame.assets.image.path);
              previewDiv.innerHTML = `<img src="/api/asset?path=${imgPath}" alt="${scene.scene_name}">`;
            }
          }
        }
      }
    } catch (error) {
      console.error(`Failed to load preview for ${scene.scene_id}:`, error);
    }
  }
}

// Navigate to scene viewer
function navigateToScene(sceneId) {
  state.isFirstRender = true;
  window.history.pushState({}, "", `/scene/${sceneId}`);
  loadScene(sceneId).then(() => {
    renderSceneViewer();
  });
}

// Render scene viewer
function renderSceneViewer() {
  const app = document.getElementById("app");

  if (!state.currentScene || !state.currentScene.frames) {
    app.innerHTML = '<div class="container"><p>Scene not found</p></div>';
    return;
  }

  const frame = state.currentScene.frames[state.currentFrameIndex];
  const totalFrames = state.currentScene.frames.length;
  const currentSceneIndex = state.scenes.findIndex(
    (s) => s.scene_id === state.currentScene.scene_id
  );
  const frameNumber = state.currentFrameIndex + 1;

  const animateClass = state.isFirstRender ? " animate-in" : "";

  let html = `
        <div class="viewer-container${animateClass}">
            <div class="viewer-header">
                <button class="back-button" onclick="goHome()">← Back to Scenes</button>
                <div class="scene-title">
                    <h2>${state.currentScene.scene_name}</h2>
                    <p class="scene-id-info">${state.currentScene.scene_id}.${frame.frame_id}</p>
                </div>
            </div>

            <div class="frame-viewer">
    `;

  // Image
  if (frame.assets && frame.assets.image) {
    const imgPath = encodeURIComponent(frame.assets.image.path);
    html += `
            <div class="frame-image-container">
                <img id="frame-image" class="frame-image" src="/api/asset?path=${imgPath}" alt="Frame ${frameNumber}">
            </div>
        `;
  } else {
    html += `
            <div class="frame-image-container">
                <div class="no-image">No image available</div>
            </div>
        `;
  }

  html += `
            </div>
    `;

  // Combined controls bar (audio + scene info + navigation)
  const hasAudio = frame.assets && frame.assets.audio;

  html += `
            <div class="controls-bar">
                <div class="controls-bar-content">
                    <div class="audio-controls">
    `;

  if (hasAudio) {
    const audioPath = encodeURIComponent(frame.assets.audio.path);
    html += `
                        <audio id="audio-player">
                            <source src="/api/asset?path=${audioPath}" type="audio/wav">
                        </audio>
                        <div class="audio-player-container">
                            <button class="play-pause-btn" id="play-pause-btn" aria-label="Play/Pause">
                                <svg id="play-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M8 5v14l11-7z"/>
                                </svg>
                                <svg id="pause-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" style="display: none;">
                                    <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"/>
                                </svg>
                            </button>
                            <div class="audio-timeline">
                                <div class="audio-progress" id="audio-progress">
                                    <div class="audio-progress-bar" id="audio-progress-bar"></div>
                                </div>
                                <div class="audio-time">
                                    <span id="current-time">0:00</span>
                                    <span id="total-time">0:00</span>
                                </div>
                            </div>
                        </div>
        `;
  } else {
    html += `
                        <div class="no-audio">No audio for this frame</div>
        `;
  }

  html += `
                    </div>
                    <div class="scene-info-bar">
                        <span class="scene-number">Scene ${
                          currentSceneIndex + 1
                        }</span>
                        <span class="frame-counter">Frame ${frameNumber} / ${totalFrames}</span>
                    </div>
                    <div class="nav-controls">
                        <button onclick="navigateFrame(-1)">
                            ← Previous
                        </button>
                        <button onclick="navigateFrame(1)">
                            Next →
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;

  app.innerHTML = html;

  // Initialize audio player if audio exists
  if (hasAudio) {
    initAudioPlayer();
  }

  // Mark that first render is complete
  if (state.isFirstRender) {
    state.isFirstRender = false;
  }
}

// Audio player functions
function initAudioPlayer() {
  const audio = document.getElementById("audio-player");
  if (!audio) return;

  // Add preload attribute to load enough data for seeking
  audio.preload = "auto";

  // Force load metadata
  audio.load();

  // Set up play/pause button
  const playPauseBtn = document.getElementById("play-pause-btn");
  if (playPauseBtn) {
    playPauseBtn.addEventListener("click", togglePlayPause);
  }

  // Set up progress bar click to seek
  const progressBar = document.getElementById("audio-progress");
  if (progressBar) {
    progressBar.addEventListener("click", seekAudio);
  }

  // Update time display when metadata loads
  audio.addEventListener("loadedmetadata", () => {
    const totalTime = document.getElementById("total-time");
    if (totalTime) {
      totalTime.textContent = formatTime(audio.duration);
    }
  });

  // Also update once data is loaded (backup)
  audio.addEventListener("loadeddata", () => {
    const totalTime = document.getElementById("total-time");
    if (totalTime && audio.duration) {
      totalTime.textContent = formatTime(audio.duration);
    }
  });

  // Update progress bar
  audio.addEventListener("timeupdate", () => {
    const progressBar = document.getElementById("audio-progress-bar");
    const currentTime = document.getElementById("current-time");

    if (progressBar && audio.duration) {
      const progress = (audio.currentTime / audio.duration) * 100;
      progressBar.style.width = `${progress}%`;
    }

    if (currentTime) {
      currentTime.textContent = formatTime(audio.currentTime);
    }
  });

  // Reset play/pause icons when audio ends
  audio.addEventListener("ended", () => {
    const playIcon = document.getElementById("play-icon");
    const pauseIcon = document.getElementById("pause-icon");
    if (playIcon && pauseIcon) {
      playIcon.style.display = "block";
      pauseIcon.style.display = "none";
    }
  });
}

function togglePlayPause() {
  const audio = document.getElementById("audio-player");
  const playIcon = document.getElementById("play-icon");
  const pauseIcon = document.getElementById("pause-icon");

  if (!audio || !playIcon || !pauseIcon) return;

  if (audio.paused) {
    audio.play();
    playIcon.style.display = "none";
    pauseIcon.style.display = "block";
  } else {
    audio.pause();
    playIcon.style.display = "block";
    pauseIcon.style.display = "none";
  }
}

function seekAudio(event) {
  const audio = document.getElementById("audio-player");
  if (!audio || !audio.duration) return;

  const rect = event.currentTarget.getBoundingClientRect();
  const pos = Math.max(
    0,
    Math.min(1, (event.clientX - rect.left) / rect.width)
  );
  audio.currentTime = pos * audio.duration;
}

function formatTime(seconds) {
  if (isNaN(seconds)) return "0:00";

  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

// Navigate between frames
function navigateFrame(delta) {
  const newIndex = state.currentFrameIndex + delta;

  if (newIndex < 0) {
    // Beginning of scene - go to previous scene
    goToPreviousScene();
    return;
  }

  if (newIndex >= state.currentScene.frames.length) {
    // End of scene - auto-advance to next scene
    autoAdvanceToNextScene();
    return;
  }

  state.currentFrameIndex = newIndex;
  renderSceneViewer();
}

// Auto-advance to next scene
function autoAdvanceToNextScene() {
  const currentIndex = state.scenes.findIndex(
    (s) => s.scene_id === state.currentScene.scene_id
  );

  if (currentIndex < state.scenes.length - 1) {
    const nextScene = state.scenes[currentIndex + 1];
    // Don't animate when advancing from one scene to another
    window.history.pushState({}, "", `/scene/${nextScene.scene_id}`);
    loadScene(nextScene.scene_id).then(() => {
      renderSceneViewer();
    });
  } else {
    // Last scene - show completion message
    alert("End of story!");
  }
}

// Go to previous scene (starting at last frame)
async function goToPreviousScene() {
  const currentIndex = state.scenes.findIndex(
    (s) => s.scene_id === state.currentScene.scene_id
  );

  if (currentIndex > 0) {
    const previousScene = state.scenes[currentIndex - 1];
    // Don't animate when going back from one scene to another
    await loadScene(previousScene.scene_id);
    // Set to last frame of previous scene
    state.currentFrameIndex = state.currentScene.frames.length - 1;
    window.history.pushState({}, "", `/scene/${previousScene.scene_id}`);
    renderSceneViewer();
  } else {
    // First scene - show message
    alert("Beginning of story!");
  }
}

function goHome() {
  window.history.pushState({}, "", "/");
  state.currentScene = null;
  state.currentFrameIndex = 0;
  state.isFirstRender = true;
  renderHome();
}

init();
