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
      class="ab-shell"
      :class="[{ shadow, loaded: isReady, playing: isPlaying, chromeHidden: !chromeVisible }]"
      @mousemove="onMouseMove"
      @mouseleave="onMouseLeave"
      @keydown.space.prevent="togglePlay"
      @keydown.m.prevent="toggleMute"
      @keydown.f.prevent="toggleFullscreen"
      tabindex="0"
      role="region"
      :aria-label="title || 'Video player'"
    >
      <!-- Poster / Overlay -->
      <button
        v-if="!isStarted"
        class="ab-overlay"
        type="button"
        :aria-label="`Play ${title || 'video'}`"
        @click="startPlayback"
      >
        <img v-if="poster" class="ab-poster" :src="poster" :alt="title || 'poster'" @load="onPosterLoad" />
        <div class="ab-gradient" aria-hidden="true" />
        <div class="ab-chrome">
          <svg class="ab-play" viewBox="0 0 64 64" aria-hidden="true">
            <circle cx="32" cy="32" r="31" class="ring" />
            <polygon points="26,20 48,32 26,44" class="triangle" />
          </svg>
          <div v-if="title" class="ab-title">{{ title }}</div>
        </div>
      </button>

      <!-- Native video -->
      <video
        v-if="mode === 'video' && isStarted"
        ref="videoEl"
        class="ab-media"
        :src="src"
        :poster="poster"
        :autoplay="autoplay"
        :muted="isMuted"
        :loop="loop"
        playsinline
        @loadedmetadata="onLoadedMeta"
        @canplay="onReady"
        @timeupdate="onTimeUpdate"
        @progress="onProgress"
        @play="() => (isPlaying = true)"
        @pause="() => (isPlaying = false)"
      />

      <!-- Iframe providers (YouTube, Vimeo) -->
      <iframe
        v-else-if="mode === 'iframe' && isStarted"
        ref="iframeEl"
        class="ab-media"
        :src="computedEmbedUrl"
        title="Video player"
        frameborder="0"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        allowfullscreen
        @load="onReady"
      />

      <!-- Loading shimmer while media initializes -->
      <div v-if="!isReady && isStarted" class="ab-loading" aria-hidden="true">
        <div class="bar" />
      </div>

      <!-- Custom Controls -->
      <div v-if="isStarted" class="ab-controls" :class="{ visible: chromeVisible }">
        <button class="ab-btn icon" @click="togglePlay" :aria-label="isPlaying ? 'Pause' : 'Play'">
          <span v-if="!isPlaying">▶</span>
          <span v-else>⏸</span>
        </button>

        <!-- Progress (native only) -->
        <div v-if="mode === 'video'" class="ab-progress" @click="onSeekClick" ref="progressEl">
          <div class="track">
            <div class="buffered" :style="{ width: bufferedPct + '%' }"></div>
            <div class="filled" :style="{ width: progressPct + '%' }"></div>
          </div>
        </div>

        <div class="ab-time" v-if="mode === 'video'">{{ timeLabel }}</div>

        <button class="ab-btn icon" @click="toggleMute" :aria-label="isMuted ? 'Unmute' : 'Mute'">
          <span v-if="isMuted">🔇</span>
          <span v-else>🔊</span>
        </button>

        <div v-if="mode === 'video'" class="ab-volume" @click.stop>
          <input type="range" min="0" max="1" step="0.01" v-model.number="volume" @input="onVolume" />
        </div>

        <button class="ab-btn icon" @click="toggleFullscreen" :aria-label="isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'">
          <span v-if="!isFullscreen">⛶</span>
          <span v-else>🞬</span>
        </button>
      </div>
    </div>

    <figcaption v-if="caption" class="ab-caption">{{ caption }}</figcaption>
  </figure>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'

type Mode = 'video' | 'iframe'

const props = withDefaults(defineProps<{
  src: string
  title?: string
  caption?: string
  poster?: string
  aspect?: string // CSS aspect-ratio value
  radius?: string // CSS border-radius value
  accent?: string // CSS color
  shadow?: boolean
  autoplay?: boolean
  muted?: boolean
  loop?: boolean
  controls?: boolean
}>(), {
  aspect: '16 / 9',
  radius: '16px',
  accent: 'var(--vp-c-brand-1, #646cff)',
  shadow: true,
  autoplay: false,
  muted: true,
  loop: false,
  controls: true,
})

const isReady = ref(false)
const isPlaying = ref(false)
const isStarted = ref(false)
const videoEl = ref<HTMLVideoElement | null>(null)
const iframeEl = ref<HTMLIFrameElement | null>(null)
const progressEl = ref<HTMLDivElement | null>(null)
const isMuted = ref(!!props.muted)
const volume = ref( props.muted ? 0 : 0.9 )
const duration = ref(0)
const current = ref(0)
const bufferedEnd = ref(0)
const chromeVisible = ref(true)
let hideTimer: number | null = null
const isFullscreen = ref(false)

const mode = computed<Mode>(() => {
  const u = props.src.toLowerCase()
  if (u.endsWith('.mp4') || u.endsWith('.webm') || u.endsWith('.ogg')) return 'video'
  if (u.includes('youtube.com') || u.includes('youtu.be') || u.includes('vimeo.com')) return 'iframe'
  // Default to iframe for unknown providers
  return u.startsWith('http') ? 'iframe' : 'video'
})

const computedEmbedUrl = computed(() => {
  if (mode.value !== 'iframe') return props.src
  const u = new URL(props.src, 'http://example.com')
  const willAutoplay = isStarted.value ? 1 : 0
  const muted = isMuted.value ? 1 : 0
  let origin = ''
  try { origin = window.location.origin } catch {}

  // YouTube normalization
  if (u.hostname.includes('youtube.com')) {
    const id = u.searchParams.get('v') || ''
    return `https://www.youtube.com/embed/${id}?autoplay=${willAutoplay}&mute=${muted}&rel=0&modestbranding=1&playsinline=1&controls=0&enablejsapi=1&origin=${encodeURIComponent(origin)}`
  }
  if (u.hostname.includes('youtu.be')) {
    const id = u.pathname.replace('/', '')
    return `https://www.youtube.com/embed/${id}?autoplay=${willAutoplay}&mute=${muted}&rel=0&modestbranding=1&playsinline=1&controls=0&enablejsapi=1&origin=${encodeURIComponent(origin)}`
  }
  // Vimeo normalization
  if (u.hostname.includes('vimeo.com')) {
    const id = u.pathname.replace('/', '')
    return `https://player.vimeo.com/video/${id}?autoplay=${willAutoplay}&muted=${muted}&title=0&byline=0&portrait=0&controls=0`
  }
  // Unknown iframe provider — forward as-is
  return props.src
})

function startPlayback() {
  isStarted.value = true
  // For native video, attempt immediate playback
  requestAnimationFrame(() => {
    if (mode.value === 'video' && videoEl.value) {
      if (props.autoplay) videoEl.value.play().catch(() => {})
      applyVolume()
    }
  })
}

function onReady() {
  isReady.value = true
}

function onPosterLoad() {
  // When poster is available, mark as visually ready for smoother transition
  isReady.value = true
}

function onLoadedMeta() {
  if (!videoEl.value) return
  duration.value = videoEl.value.duration || 0
}

function onTimeUpdate() {
  if (!videoEl.value) return
  current.value = videoEl.value.currentTime || 0
}

function onProgress() {
  const v = videoEl.value
  if (!v || v.buffered.length === 0) return
  bufferedEnd.value = v.buffered.end(v.buffered.length - 1)
}

const progressPct = computed(() => duration.value ? (current.value / duration.value) * 100 : 0)
const bufferedPct = computed(() => {
  if (!duration.value) return 0
  return Math.min(100, (bufferedEnd.value / duration.value) * 100)
})

const timeLabel = computed(() => `${fmt(current.value)} / ${fmt(duration.value)}`)
function fmt(s: number) {
  if (!isFinite(s)) return '0:00'
  const m = Math.floor(s / 60)
  const r = Math.floor(s % 60)
  return `${m}:${String(r).padStart(2,'0')}`
}

function togglePlay() {
  if (!isStarted.value) return startPlayback()
  if (mode.value === 'video' && videoEl.value) {
    if (videoEl.value.paused) videoEl.value.play()
    else videoEl.value.pause()
  } else if (mode.value === 'iframe') {
    // Basic play/pause via postMessage for YouTube/Vimeo when possible
    tryIframeCommand(isPlaying.value ? 'pause' : 'play')
    isPlaying.value = !isPlaying.value
  }
}

function toggleMute() {
  isMuted.value = !isMuted.value
  if (mode.value === 'video') applyVolume()
  else tryIframeCommand(isMuted.value ? 'mute' : 'unmute')
}

function onVolume() {
  if (volume.value > 0 && isMuted.value) isMuted.value = false
  applyVolume()
}

function applyVolume() {
  const v = videoEl.value
  if (!v) return
  v.muted = isMuted.value
  v.volume = isMuted.value ? 0 : Math.min(1, Math.max(0, volume.value))
}

function onSeekClick(e: MouseEvent) {
  if (mode.value !== 'video' || !progressEl.value || !videoEl.value || !duration.value) return
  const rect = progressEl.value.getBoundingClientRect()
  const pct = (e.clientX - rect.left) / rect.width
  videoEl.value.currentTime = Math.max(0, Math.min(duration.value, duration.value * pct))
}

function onMouseMove() {
  chromeVisible.value = true
  if (hideTimer) window.clearTimeout(hideTimer)
  hideTimer = window.setTimeout(() => (chromeVisible.value = false), 1800)
}
function onMouseLeave() {
  chromeVisible.value = false
  if (hideTimer) window.clearTimeout(hideTimer)
}

function toggleFullscreen() {
  const el = (videoEl.value?.parentElement) as HTMLElement | null
  if (!el) return
  if (!document.fullscreenElement) {
    el.requestFullscreen?.()
    isFullscreen.value = true
  } else {
    document.exitFullscreen?.()
    isFullscreen.value = false
  }
}

function tryIframeCommand(cmd: 'play' | 'pause' | 'mute' | 'unmute') {
  // Only implement basic commands for YouTube/Vimeo
  const target = iframeEl.value
  if (!target) return

  try {
    const src = target.src
    if (src.includes('youtube.com/embed')) {
      const msg = { event: 'command', func: cmd === 'play' ? 'playVideo' : cmd === 'pause' ? 'pauseVideo' : cmd === 'mute' ? 'mute' : 'unMute', args: [] }
      target.contentWindow?.postMessage(JSON.stringify(msg), '*')
    } else if (src.includes('player.vimeo.com')) {
      const msg = cmd === 'play' ? { method: 'play' } : cmd === 'pause' ? { method: 'pause' } : cmd === 'mute' ? { method: 'setVolume', value: 0 } : { method: 'setVolume', value: volume.value }
      target.contentWindow?.postMessage(msg, '*')
    }
  } catch {}
}

let fsHandler: ((this: Document, ev: Event) => any) | null = null
onMounted(() => {
  fsHandler = () => { isFullscreen.value = !!document.fullscreenElement }
  document.addEventListener('fullscreenchange', fsHandler)
})

onBeforeUnmount(() => {
  if (hideTimer) window.clearTimeout(hideTimer)
  if (fsHandler) document.removeEventListener('fullscreenchange', fsHandler)
})
</script>

<style scoped>
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
  transition: box-shadow .3s ease, transform .3s ease;
}
.ab-shell.shadow {
  box-shadow: 0 12px 30px rgba(0,0,0,.35), 0 2px 8px rgba(0,0,0,.25);
}
.ab-shell.loaded:hover {
  transform: translateY(-1px);
  box-shadow: 0 16px 40px rgba(0,0,0,.4), 0 4px 12px rgba(0,0,0,.28);
}

.ab-media {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  background: #000;
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
  transition: filter .4s ease;
}
.ab-overlay:hover .ab-poster {
  filter: saturate(1) brightness(1.02);
}

.ab-gradient {
  position: absolute;
  inset: 0;
  background: radial-gradient(120% 120% at 50% 50%, rgba(0,0,0,0) 40%, rgba(0,0,0,.45) 100%),
              linear-gradient(180deg, rgba(0,0,0,0) 55%, rgba(0,0,0,.6) 100%);
  pointer-events: none;
}

.ab-chrome {
  position: relative;
  z-index: 2;
  display: grid;
  place-items: center;
  gap: 16px;
  transform: translateY(0);
  transition: transform .35s ease;
}
.ab-overlay:hover .ab-chrome {
  transform: translateY(-2px);
}

.ab-play {
  width: 84px;
  height: 84px;
  filter: drop-shadow(0 6px 18px rgba(0,0,0,.45));
}
.ab-play .ring {
  fill: rgba(255,255,255,.06);
  stroke: var(--ab-accent);
  stroke-width: 2;
}
.ab-play .triangle {
  fill: white;
  transform-origin: 50% 50%;
  transition: transform .25s ease;
}
.ab-overlay:hover .ab-play .triangle {
  transform: scale(1.05);
}

.ab-title {
  color: white;
  font-weight: 600;
  letter-spacing: .2px;
  text-shadow: 0 2px 10px rgba(0,0,0,.45);
  padding: 6px 10px;
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(0,0,0,.28) 0%, rgba(0,0,0,.55) 100%);
}

.ab-loading {
  position: absolute;
  inset: 0;
  overflow: hidden;
}
.ab-loading .bar {
  position: absolute;
  bottom: 0;
  left: 0;
  height: 3px;
  width: 40%;
  background: linear-gradient(90deg, transparent, var(--ab-accent), transparent);
  animation: ab-scan 1.2s ease-in-out infinite;
}

@keyframes ab-scan {
  0% { transform: translateX(-100%); opacity: .2; }
  50% { opacity: .9; }
  100% { transform: translateX(250%); opacity: .2; }
}

/* Controls */
.ab-controls {
  position: absolute;
  inset: auto 0 0 0;
  display: grid;
  grid-template-columns: auto 1fr auto auto auto;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: rgba(10, 10, 14, 0.35);
  backdrop-filter: saturate(140%) blur(10px);
  transform: translateY(100%);
  opacity: 0;
  transition: transform .28s ease, opacity .28s ease;
  will-change: transform, opacity;
}
.ab-shell:hover .ab-controls,
.ab-controls.visible {
  transform: translateY(0%);
  opacity: 1;
}
.ab-shell.chromeHidden .ab-controls {
  transform: translateY(100%);
  opacity: 0;
}

.ab-btn {
  appearance: none;
  border: none;
  background: transparent;
  color: #fff;
  padding: 6px 8px;
  border-radius: 10px;
  transition: background .2s ease;
}
.ab-btn:hover { background: rgba(255,255,255,.08); }
.ab-btn:active { background: rgba(255,255,255,.12); }
.ab-btn:focus-visible { outline: 2px solid var(--ab-accent); outline-offset: 3px; }

.ab-progress {
  height: 26px;
  display: grid;
  align-items: center;
}
.ab-progress .track {
  position: relative;
  height: 4px;
  border-radius: 999px;
  background: rgba(255,255,255,.18);
  overflow: hidden;
}
.ab-progress .buffered {
  position: absolute;
  top: 0; left: 0; bottom: 0;
  background: rgba(255,255,255,.28);
}
.ab-progress .filled {
  position: absolute;
  top: 0; left: 0; bottom: 0;
  background: linear-gradient(90deg, var(--ab-accent), color-mix(in srgb, var(--ab-accent) 65%, #ffffff));
}

.ab-time { color: rgba(255,255,255,.85); font-variant-numeric: tabular-nums; font-size: 12px; }

.ab-volume { width: 90px; }
.ab-volume input[type="range"] {
  -webkit-appearance: none;
  width: 100%; height: 4px;
  background: rgba(255,255,255,.18);
  border-radius: 999px;
  outline: none;
}
.ab-volume input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px; height: 14px;
  border-radius: 50%;
  background: var(--ab-accent);
  box-shadow: 0 2px 6px rgba(0,0,0,.35);
  margin-top: -5px;
}
.ab-volume input[type="range"]::-moz-range-thumb {
  width: 14px; height: 14px;
  border-radius: 50%;
  background: var(--ab-accent);
  border: none;
}

@media (prefers-reduced-motion: reduce) {
  .ab-shell, .ab-controls { transition: none; }
  .ab-overlay .ab-chrome, .ab-play .triangle { transition: none; }
}
</style>
