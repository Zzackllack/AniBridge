<script setup lang="ts">
import { OAOperation } from 'vitepress-openapi/client'
import { useData } from 'vitepress'

const { params } = useData()
</script>

<template>
  <ClientOnly>
    <template #fallback>
      <p>Loading endpoint reference…</p>
    </template>

    <OAOperation
      :operation-id="params.operationId"
      :prefix-headings="true"
      hide-branding
    />
  </ClientOnly>
</template>
