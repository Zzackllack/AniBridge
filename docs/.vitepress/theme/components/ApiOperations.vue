<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vitepress'

import spec from '../../../src/openapi.json'

type HttpMethod = 'get' | 'post' | 'put' | 'patch' | 'delete' | 'options' | 'head'

type OpenAPIOperationObject = {
  operationId?: string
  summary?: string
  tags?: string[]
}

type OpenAPIPathItemObject = Partial<Record<HttpMethod, OpenAPIOperationObject>>

type OpenAPISpec = {
  paths?: Record<string, OpenAPIPathItemObject>
}

type OperationEntry = {
  operationId: string
  method: HttpMethod
  path: string
  summary?: string
  tags: string[]
}

const props = withDefaults(
  defineProps<{
    tags?: string[]
    /** Auto-navigate to the first matching operation page. */
    redirect?: boolean
    /** When true, show the short summary next to the operation name. */
    showSummary?: boolean
  }>(),
  {
    redirect: false,
    showSummary: false,
  },
)

const router = useRouter()

const allOperations = computed<OperationEntry[]>(() => {
  const methods: HttpMethod[] = ['get', 'post', 'put', 'patch', 'delete', 'options', 'head']
  const out: OperationEntry[] = []

  const paths = (spec as OpenAPISpec).paths ?? {}
  for (const [path, def] of Object.entries(paths)) {
    for (const method of methods) {
      const op = def?.[method]
      if (!op?.operationId) continue
      out.push({
        operationId: op.operationId,
        method,
        path,
        summary: op.summary,
        tags: Array.isArray(op.tags) && op.tags.length ? op.tags : ['General'],
      })
    }
  }

  return out
})

const filteredOperations = computed(() => {
  const tags = props.tags?.length ? new Set(props.tags) : null
  const ops = tags
    ? allOperations.value.filter((o) => o.tags.some((t) => tags.has(t)))
    : allOperations.value.slice()

  // Stable ordering: tag, then path, then method.
  const methodRank: Record<HttpMethod, number> = {
    get: 1,
    post: 2,
    put: 3,
    patch: 4,
    delete: 5,
    options: 6,
    head: 7,
  }

  ops.sort((a, b) => {
    const at = a.tags[0] || 'General'
    const bt = b.tags[0] || 'General'
    if (at !== bt) return at.localeCompare(bt)
    if (a.path !== b.path) return a.path.localeCompare(b.path)
    return methodRank[a.method] - methodRank[b.method]
  })

  return ops
})

const groupedByTag = computed(() => {
  const groups = new Map<string, OperationEntry[]>()
  for (const op of filteredOperations.value) {
    // Intentionally show multi-tag operations under each matching tag.
    // This improves discoverability when users browse by domain area.
    for (const tag of op.tags.length ? op.tags : ['General']) {
      if (props.tags?.length && !props.tags.includes(tag)) continue
      const list = groups.get(tag) ?? []
      list.push(op)
      groups.set(tag, list)
    }
  }

  return Array.from(groups.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([tag, ops]) => ({ tag, ops }))
})

function hrefFor(operationId: string) {
  return `/api/operations/${operationId}`
}

const shouldOpenGroups = computed(() => Boolean(props.tags?.length))

onMounted(() => {
  if (!props.redirect) return
  const first = filteredOperations.value[0]
  if (!first) return
  router.go(hrefFor(first.operationId))
})
</script>

<template>
  <div class="api-ops">
    <p v-if="redirect" class="hint">
      Redirecting to the first operation…
    </p>

    <template v-if="groupedByTag.length">
      <details v-for="g in groupedByTag" :key="g.tag" class="group" :open="shouldOpenGroups">
        <summary class="groupTitle">
          {{ g.tag }} <span class="count">({{ g.ops.length }})</span>
        </summary>
        <ul class="items">
          <li v-for="op in g.ops" :key="op.operationId" class="item">
            <!-- Provided globally by vitepress-openapi via OpenAPITheme.enhanceApp -->
            <OAOperationLink
              :href="hrefFor(op.operationId)"
              :method="op.method"
              :title="op.summary || `${op.method.toUpperCase()} ${op.path}`"
            />
            <span v-if="showSummary && op.summary" class="summary">
              — {{ op.summary }}
            </span>
          </li>
        </ul>
      </details>
    </template>

    <p v-else class="empty">No operations found.</p>
  </div>
</template>

<style scoped>
.api-ops {
  margin-top: 12px;
}

.hint {
  color: var(--vp-c-text-2);
  font-size: 0.95rem;
}

.group {
  border: 1px solid var(--vp-c-divider);
  border-radius: 10px;
  padding: 10px 12px;
  margin: 10px 0;
  background: var(--vp-c-bg-soft);
}

.groupTitle {
  cursor: pointer;
  font-weight: 600;
}

.count {
  color: var(--vp-c-text-2);
  font-weight: 500;
  margin-left: 6px;
}

.items {
  list-style: none;
  padding: 8px 0 0;
  margin: 0;
}

.item {
  padding: 6px 0;
}

.summary {
  color: var(--vp-c-text-2);
  font-size: 0.95rem;
  margin-left: 6px;
}

.empty {
  color: var(--vp-c-text-2);
}
</style>
