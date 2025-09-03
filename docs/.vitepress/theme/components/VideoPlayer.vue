<template>
  <figure
    class="ab-video"
    :style="{
      '--ab-aspect': aspect,
      '--ab-radius': radius,
      '--ab-accent': accent,
    }"
  >
    <div
      ref="shellEl"
      class="ab-shell"
      :class="[{ shadow }]"
      tabindex="0"
      role="region"
      :aria-label="title || 'Video player'"
      @keydown="onKeydown"
    >
      <!-- Poster / Overlay -->
      <button
        v-show="showOverlay"
        class="ab-overlay"
        type="button"
        :aria-label="`Play ${title || 'video'}`"
        @click="startPlaybackFromOverlay"
      >
        <img
          v-if="poster"
          class="ab-poster"
          :src="poster"
          :alt="title || 'poster'"
        />
        <div class="ab-gradient" aria-hidden="true" />
        <div class="ab-chrome">
          <svg class="ab-play" viewBox="0 0 64 64" aria-hidden="true">
            <circle cx="32" cy="32" r="31" class="ring" />
            <polygon points="26,20 48,32 26,44" class="triangle" />
          </svg>
          <div v-if="title" class="ab-title">{{ title }}</div>
        </div>
      </button>

      <!-- Video -->
      <video
        ref="videoEl"
        class="ab-media"
        :src="src"
        :poster="poster"
        :muted="isMuted"
        :loop="looping"
        playsinline
        preload="metadata"
        @loadedmetadata="onLoadedMetadata"
        @timeupdate="onTimeUpdate"
        @progress="onProgress"
        @play="onPlay"
        @pause="onPause"
        @ended="onEnded"
        @volumechange="onVolumeChange"
        @error="onError"
      />

      <!-- Controls -->
      <div class="ab-controls visible">
        <!-- Play/Pause -->
        <button class="ab-btn icon" :aria-label="isPlaying ? 'Pause' : 'Play'" @click="togglePlay">
          <Pause v-if="isPlaying" class="ab-icon" aria-hidden="true" />
          <Play v-else class="ab-icon" aria-hidden="true" />
        </button>

        <!-- Progress / Scrubber -->
        <div
          class="ab-progress"
          role="slider"
          aria-label="Seek"
          :aria-valuemin="0"
          :aria-valuemax="duration"
          :aria-valuenow="scrubTime ?? currentTime"
          :aria-valuetext="formatTime(scrubTime ?? currentTime)"
        >
          <div
            ref="trackEl"
            class="track"
            @pointerdown="onTrackPointerDown"
          >
            <div class="buffered" :style="{ width: bufferedPct + '%' }"></div>
            <div class="filled" :style="{ width: progressPct + '%' }"></div>
            <div class="handle" :style="{ left: progressPct + '%' }"></div>
          </div>
        </div>

        <!-- Time -->
        <div class="ab-time">{{ formatTime(currentTime) }} / {{ formatTime(duration) }}</div>

        <!-- Mute -->
        <button class="ab-btn icon" :aria-label="isMuted ? 'Unmute' : 'Mute'" @click="toggleMute">
          <VolumeX v-if="isMuted" class="ab-icon" aria-hidden="true" />
          <Volume2 v-else class="ab-icon" aria-hidden="true" />
        </button>

        <!-- Volume -->
        <div class="ab-volume">
          <input
            type="range"
            min="0"
            max="1"
            step="0.01"
            :value="volume"
            aria-label="Volume"
            @input="onVolumeInput"
          />
        </div>

        <!-- Loop -->
        <button
          class="ab-btn icon"
          :aria-pressed="looping ? 'true' : 'false'"
          :aria-label="looping ? 'Disable loop' : 'Enable loop'"
          @click="toggleLoop"
        >
          <Repeat class="ab-icon" aria-hidden="true" />
        </button>

        <!-- Fullscreen -->
        <button
          class="ab-btn icon"
          :aria-label="isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'"
          @click="toggleFullscreen"
        >
          <Minimize v-if="isFullscreen" class="ab-icon" aria-hidden="true" />
          <Maximize v-else class="ab-icon" aria-hidden="true" />
        </button>
      </div>
    </div>

    <figcaption v-if="caption" class="ab-caption">{{ caption }}</figcaption>
  </figure>
</template>

<script setup lang="ts">
import {
  Maximize,
  Minimize,
  Play,
  Pause,
  Volume2,
  VolumeX,
  Repeat,
} from "lucide-vue-next";
import {
  defineProps,
  withDefaults,
  defineEmits,
  ref,
  computed,
  watch,
  onMounted,
  onBeforeUnmount,
  nextTick,
} from "vue";

const props = withDefaults(
  defineProps<{
    src: string;
    title?: string;
    caption?: string;
    poster?: string;
    aspect?: string; // CSS aspect-ratio value
    radius?: string; // CSS border-radius value
    accent?: string; // CSS color
    shadow?: boolean;

    autoplay?: boolean;
    muted?: boolean;
    loop?: boolean;
  }>(),
  {
    aspect: "16 / 9",
    radius: "16px",
    accent: "var(--vp-c-brand-1, #646cff)",
    shadow: true,
    autoplay: false,
    muted: false,
    loop: false,
  }
);

const emit = defineEmits<{
  (e: "play"): void;
  (e: "pause"): void;
  (e: "ended"): void;
  (e: "timeupdate", t: number): void;
  (e: "loadedmetadata", d: number): void;
  (e: "seeking", t: number): void;
  (e: "seeked", t: number): void;
  (e: "volumechange", v: number, muted: boolean): void;
  (e: "enterfullscreen"): void;
  (e: "exitfullscreen"): void;
  (e: "error", err: unknown): void;
}>();

const videoEl = ref<HTMLVideoElement | null>(null);
const trackEl = ref<HTMLElement | null>(null);
const shellEl = ref<HTMLElement | null>(null);

const isPlaying = ref(false);
const duration = ref(0);
const currentTime = ref(0);

const isMuted = ref(!!props.muted);
const volume = ref(0.9);
const lastVolume = ref(0.9);

const bufferedEnd = ref(0);

const looping = ref(!!props.loop);
const isFullscreen = ref(false);
const showOverlay = ref(!props.autoplay); // Overlay nur bis zum ersten Start

// Scrubbing state
const isScrubbing = ref(false);
const scrubTime = ref<number | null>(null);
let wasPlayingBeforeScrub = false;

const progressPct = computed(() =>
  duration.value ? ((scrubTime.value ?? currentTime.value) / duration.value) * 100 : 0
);
const bufferedPct = computed(() =>
  duration.value ? (bufferedEnd.value / duration.value) * 100 : 0
);

function formatTime(t: number) {
  if (!isFinite(t) || t < 0) return "0:00";
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

async function attemptAutoplay() {
  if (!videoEl.value) return;
  try {
    videoEl.value.muted = isMuted.value || true; // Browser-Autoplay-Schutz
    if (props.autoplay) {
      await videoEl.value.play();
      showOverlay.value = false;
    }
  } catch {
    // Autoplay blockiert -> Overlay bleibt sichtbar
  } finally {
    // setze gewünschtes Muted nach Autoplay-Versuch
    videoEl.value.muted = isMuted.value;
  }
}

function togglePlay() {
  const v = videoEl.value;
  if (!v) return;
  if (v.paused) {
    v.play().then(() => (showOverlay.value = false)).catch(() => {});
  } else {
    v.pause();
  }
}

function onPlay() {
  isPlaying.value = true;
  emit("play");
}
function onPause() {
  isPlaying.value = false;
  emit("pause");
}
function onEnded() {
  emit("ended");
  if (!looping.value) {
    // "Exit": zurück zum Overlay & Anfang
    showOverlay.value = true;
    currentTime.value = 0;
    if (videoEl.value) videoEl.value.currentTime = 0;
  }
}
function onError(e: Event) {
  emit("error", e);
}

function onLoadedMetadata() {
  if (!videoEl.value) return;
  duration.value = videoEl.value.duration || 0;
  emit("loadedmetadata", duration.value);
}

function onTimeUpdate() {
  if (!videoEl.value || isScrubbing.value) return;
  currentTime.value = videoEl.value.currentTime;
  emit("timeupdate", currentTime.value);
}

function calcBufferedEnd() {
  const v = videoEl.value;
  if (!v) return 0;
  const ranges = v.buffered;
  if (!ranges || ranges.length === 0) return 0;
  // nimm die Range, die den aktuellen Zeitpunkt enthält – sonst die letzte
  for (let i = 0; i < ranges.length; i++) {
    if (v.currentTime >= ranges.start(i) && v.currentTime <= ranges.end(i)) {
      return ranges.end(i);
    }
  }
  return ranges.end(ranges.length - 1);
}

function onProgress() {
  bufferedEnd.value = calcBufferedEnd();
}

function setTimeFromClientX(clientX: number) {
  if (!trackEl.value || !duration.value) return 0;
  const rect = trackEl.value.getBoundingClientRect();
  const ratio = Math.min(Math.max(0, (clientX - rect.left) / rect.width), 1);
  const t = ratio * duration.value;
  scrubTime.value = t;
  emit("seeking", t);
  return t;
}

function onTrackPointerDown(e: PointerEvent) {
  if (!videoEl.value) return;
  (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
  isScrubbing.value = true;
  wasPlayingBeforeScrub = !videoEl.value.paused;
  if (wasPlayingBeforeScrub) videoEl.value.pause();

  setTimeFromClientX(e.clientX);
  window.addEventListener("pointermove", onPointerMove);
  window.addEventListener("pointerup", onPointerUp);
}

function onPointerMove(e: PointerEvent) {
  setTimeFromClientX(e.clientX);
}

function onPointerUp(e: PointerEvent) {
  const v = videoEl.value;
  if (!v) return;

  const t = setTimeFromClientX(e.clientX);
  v.currentTime = t;
  currentTime.value = t;
  emit("seeked", t);

  isScrubbing.value = false;
  scrubTime.value = null;

  window.removeEventListener("pointermove", onPointerMove);
  window.removeEventListener("pointerup", onPointerUp);

  if (wasPlayingBeforeScrub) {
    v.play().catch(() => {});
  }
}

function onVolumeInput(e: Event) {
  const v = (e.target as HTMLInputElement).valueAsNumber;
  setVolume(v);
}

function setVolume(v: number) {
  const vClamped = Math.min(Math.max(v, 0), 1);
  volume.value = vClamped;
  const vid = videoEl.value;
  if (vid) vid.volume = vClamped;

  if (vClamped === 0) {
    isMuted.value = true;
    if (vid) vid.muted = true;
  } else {
    if (!isMuted.value) lastVolume.value = vClamped;
    if (vid) vid.muted = false;
    isMuted.value = false;
    lastVolume.value = vClamped;
  }
  emit("volumechange", volume.value, isMuted.value);
}

function toggleMute() {
  const vid = videoEl.value;
  if (!vid) return;
  if (isMuted.value || vid.volume === 0) {
    setVolume(lastVolume.value || 0.5);
    vid.muted = false;
    isMuted.value = false;
  } else {
    lastVolume.value = volume.value;
    setVolume(0);
    vid.muted = true;
    isMuted.value = true;
  }
}

function onVolumeChange() {
  const vid = videoEl.value;
  if (!vid) return;
  isMuted.value = vid.muted || vid.volume === 0;
  volume.value = vid.volume;
  emit("volumechange", volume.value, isMuted.value);
}

function toggleLoop() {
  looping.value = !looping.value;
}

function startPlaybackFromOverlay() {
  togglePlay();
}

function onKeydown(e: KeyboardEvent) {
  const key = e.code;
  if (["Space", "KeyK"].includes(key)) {
    e.preventDefault();
    togglePlay();
  } else if (key === "KeyM") {
    toggleMute();
  } else if (key === "KeyF") {
    toggleFullscreen();
  } else if (key === "ArrowRight") {
    seekBy(5);
  } else if (key === "ArrowLeft") {
    seekBy(-5);
  } else if (key === "ArrowUp") {
    e.preventDefault();
    setVolume(Math.min(volume.value + 0.05, 1));
  } else if (key === "ArrowDown") {
    e.preventDefault();
    setVolume(Math.max(volume.value - 0.05, 0));
  } else if (key === "KeyL") {
    toggleLoop();
  }
}

function seekBy(delta: number) {
  const v = videoEl.value;
  if (!v) return;
  const t = Math.min(Math.max(0, v.currentTime + delta), duration.value || v.duration || 0);
  v.currentTime = t;
  currentTime.value = t;
  emit("timeupdate", t);
}

function toggleFullscreen() {
  const el = shellEl.value as HTMLElement | null;
  if (!el) return;
  if (!document.fullscreenElement) {
    el.requestFullscreen?.().then(() => {
      isFullscreen.value = true;
      emit("enterfullscreen");
    }).catch(() => {});
  } else {
    document.exitFullscreen?.().then(() => {
      isFullscreen.value = false;
      emit("exitfullscreen");
    }).catch(() => {});
  }
}

function onFullscreenChange() {
  isFullscreen.value = !!document.fullscreenElement;
}

watch(
  () => props.src,
  async () => {
    // Reset state on source change
    currentTime.value = 0;
    duration.value = 0;
    bufferedEnd.value = 0;
    showOverlay.value = !props.autoplay;
    await nextTick();
    // reload and optionally autoplay
    attemptAutoplay();
  }
);

watch(
  () => props.muted,
  (m) => {
    isMuted.value = !!m;
    if (videoEl.value) videoEl.value.muted = !!m;
  }
);

watch(
  () => props.loop,
  (l) => {
    looping.value = !!l;
  }
);

onMounted(() => {
  if (videoEl.value) {
    // initial volume (respect muted prop)
    isMuted.value = !!props.muted;
    if (isMuted.value) {
      videoEl.value.muted = true;
      videoEl.value.volume = 0;
      volume.value = 0;
    } else {
      videoEl.value.volume = volume.value;
    }
  }
  attemptAutoplay();
  document.addEventListener("fullscreenchange", onFullscreenChange);
});

onBeforeUnmount(() => {
  document.removeEventListener("fullscreenchange", onFullscreenChange);
  window.removeEventListener("pointermove", onPointerMove);
  window.removeEventListener("pointerup", onPointerUp);
});
</script>

<style scoped>
/* --- dein ursprüngliches Styling unverändert übernommen --- */
.ab-video {
  display: grid;
  gap: 10px;
}
.ab-caption {
  color: var(--vp-c-text-2);
  font-size: 0.925rem;
  line-height: 1.4;
  text-align: center;
}

.ab-shell {
  position: relative;
  aspect-ratio: var(--ab-aspect);
  border-radius: var(--ab-radius);
  overflow: clip;
  background: linear-gradient(180deg, #0b0b12 0%, #101018 100%);
  transition: box-shadow 0.3s ease, transform 0.3s ease;
}
.ab-shell.shadow {
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.35), 0 2px 8px rgba(0, 0, 0, 0.25);
}
.ab-shell:hover {
  transform: translateY(-1px);
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.4), 0 4px 12px rgba(0, 0, 0, 0.28);
}

.ab-media {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  background: #000;
  z-index: 1;
}

.ab-overlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  border: 0;
  padding: 0;
  background: transparent;
  cursor: pointer;
  z-index: 5;
}
.ab-overlay:focus-visible {
  outline: 2px solid var(--ab-accent);
  outline-offset: 4px;
}

.ab-poster {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  filter: saturate(0.9);
  transition: filter 0.4s ease;
}
.ab-overlay:hover .ab-poster {
  filter: saturate(1) brightness(1.02);
}

.ab-gradient {
  position: absolute;
  inset: 0;
  background: radial-gradient(
      120% 120% at 50% 50%,
      rgba(0, 0, 0, 0) 40%,
      rgba(0, 0, 0, 0.45) 100%
    ),
    linear-gradient(180deg, rgba(0, 0, 0, 0) 55%, rgba(0, 0, 0, 0.6) 100%);
  pointer-events: none;
}

.ab-chrome {
  position: relative;
  z-index: 2;
  display: grid;
  place-items: center;
  gap: 16px;
  transform: translateY(0);
  transition: transform 0.35s ease;
}
.ab-overlay:hover .ab-chrome {
  transform: translateY(-2px);
}

.ab-play {
  width: 84px;
  height: 84px;
  filter: drop-shadow(0 6px 18px rgba(0, 0, 0, 0.45));
}
.ab-play .ring {
  fill: rgba(255, 255, 255, 0.06);
  stroke: var(--ab-accent);
  stroke-width: 2;
}
.ab-play .triangle {
  fill: white;
  transform-origin: 50% 50%;
  transition: transform 0.25s ease;
}
.ab-overlay:hover .ab-play .triangle {
  transform: scale(1.05);
}

.ab-title {
  color: white;
  font-weight: 600;
  letter-spacing: 0.2px;
  text-shadow: 0 2px 10px rgba(0, 0, 0, 0.45);
  padding: 6px 10px;
  border-radius: 8px;
  background: linear-gradient(
    180deg,
    rgba(0, 0, 0, 0.28) 0%,
    rgba(0, 0, 0, 0.55) 100%
  );
}

/* Controls */
.ab-controls {
  position: absolute;
  inset: auto 0 0 0;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: rgba(10, 10, 14, 0.35);
  backdrop-filter: saturate(140%) blur(10px);
  transform: translateY(100%);
  opacity: 0;
  transition: transform 0.28s ease, opacity 0.28s ease;
  will-change: transform, opacity;
  z-index: 4;
}
.ab-shell:hover .ab-controls,
.ab-controls.visible {
  transform: translateY(0%);
  opacity: 1;
}

.ab-btn {
  appearance: none;
  border: none;
  background: transparent;
  color: #fff;
  padding: 6px 8px;
  border-radius: 10px;
  transition: background 0.2s ease;
}
.ab-btn:hover {
  background: rgba(255, 255, 255, 0.08);
}
.ab-btn:active {
  background: rgba(255, 255, 255, 0.12);
}
.ab-btn:focus-visible {
  outline: 2px solid var(--ab-accent);
  outline-offset: 3px;
}

.ab-icon {
  width: 18px;
  height: 18px;
  stroke: #fff;
  stroke-width: 2px;
}

.ab-progress {
  height: 28px;
  display: grid;
  align-items: center;
  flex: 1;
}
.ab-progress .track {
  position: relative;
  height: 4px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.18);
  overflow: hidden;
  cursor: pointer;
  user-select: none;
  touch-action: none;
}
.ab-progress .buffered {
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.28);
}
.ab-progress .filled {
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  background: linear-gradient(
    90deg,
    var(--ab-accent),
    color-mix(in srgb, var(--ab-accent) 65%, #ffffff)
  );
}

.ab-progress .handle {
  position: absolute;
  top: 50%;
  width: 14px;
  height: 14px;
  transform: translate(-50%, -50%);
  background: #fff;
  border: 2px solid var(--ab-accent);
  border-radius: 50%;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.35);
  opacity: 0;
  transition: opacity 0.15s ease;
  pointer-events: none;
}
.ab-progress:hover .handle {
  opacity: 1;
}

.ab-time {
  color: rgba(255, 255, 255, 0.85);
  font-variant-numeric: tabular-nums;
  font-size: 12px;
}

.ab-volume {
  width: 110px;
  display: grid;
  align-items: center;
}
.ab-volume input[type="range"] {
  -webkit-appearance: none;
  width: 100%;
  height: 28px;
  background: transparent;
  border-radius: 999px;
  outline: none;
}
.ab-volume input[type="range"]::-webkit-slider-runnable-track {
  height: 4px;
  background: rgba(255, 255, 255, 0.18);
  border-radius: 999px;
}
.ab-volume input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--ab-accent);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.35);
  margin-top: -5px;
}
.ab-volume input[type="range"]::-moz-range-track {
  height: 4px;
  background: rgba(255, 255, 255, 0.18);
  border-radius: 999px;
}
.ab-volume input[type="range"]::-moz-range-thumb {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--ab-accent);
  border: none;
}

@media (prefers-reduced-motion: reduce) {
  .ab-shell,
  .ab-controls {
    transition: none;
  }
  .ab-overlay .ab-chrome,
  .ab-play .triangle {
    transition: none;
  }
}
</style>
