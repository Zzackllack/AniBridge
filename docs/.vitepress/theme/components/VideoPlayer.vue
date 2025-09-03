<template>
  <figure
    class="ab-video"
    :style="{
      '--ab-aspect': aspect,
      '--ab-radius': radius,
      '--ab-accent': accent,
    }"
  >
    <div class="ab-shell" :class="[{ shadow, loaded: isReady, playing: isPlaying }]">
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
        :muted="muted"
        :loop="loop"
        :controls="controls"
        playsinline
        @canplay="onReady"
        @play="() => (isPlaying = true)"
        @pause="() => (isPlaying = false)"
      />

      <!-- Iframe providers (YouTube, Vimeo) -->
      <iframe
        v-else-if="mode === 'iframe' && isStarted"
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
    </div>

    <figcaption v-if="caption" class="ab-caption">{{ caption }}</figcaption>
  </figure>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

type Mode = 'video' | 'iframe'

const props = withDefaults(defineProps<{
  src: string
  title?: string
  caption?: string
  poster?: string
  aspect?: string // CSS aspect-ratio value
  radius?: string // CSS border-radius value
  accent?: string // CSS color
  autoplay?: boolean
  muted?: boolean
  loop?: boolean
  controls?: boolean
}>(), {
  aspect: '16 / 9',
  radius: '16px',
  accent: '#7c5cff',
  autoplay: false,
  muted: true,
  loop: false,
  controls: true,
})

const isReady = ref(false)
const isPlaying = ref(false)
const isStarted = ref(false)
const videoEl = ref<HTMLVideoElement | null>(null)

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
  const autoplay = props.autoplay || true // when entering iframe mode on click we want autoplay
  const muted = props.muted ? 1 : 0

  // YouTube normalization
  if (u.hostname.includes('youtube.com')) {
    const id = u.searchParams.get('v') || ''
    return `https://www.youtube.com/embed/${id}?autoplay=${autoplay ? 1 : 0}&mute=${muted}&rel=0&modestbranding=1`
  }
  if (u.hostname.includes('youtu.be')) {
    const id = u.pathname.replace('/', '')
    return `https://www.youtube.com/embed/${id}?autoplay=${autoplay ? 1 : 0}&mute=${muted}&rel=0&modestbranding=1`
  }
  // Vimeo normalization
  if (u.hostname.includes('vimeo.com')) {
    const id = u.pathname.replace('/', '')
    return `https://player.vimeo.com/video/${id}?autoplay=${autoplay ? 1 : 0}&muted=${muted}&title=0&byline=0&portrait=0`
  }
  // Unknown iframe provider — forward as-is
  return props.src
})

function startPlayback() {
  isStarted.value = true
  // For native video, attempt immediate playback
  requestAnimationFrame(() => {
    if (mode.value === 'video' && videoEl.value) {
      if (props.autoplay) {
        videoEl.value.play().catch(() => {})
      }
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

onMounted(() => {
  // No-op; SSR safety hook reserved for future use
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
</style>

