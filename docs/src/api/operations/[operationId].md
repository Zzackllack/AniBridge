---
title: "{{ $params.pageTitle }}"
outline: false
aside: false
---

<script setup lang="ts">
import { useData } from 'vitepress'

const { params } = useData()
</script>

<!-- Provided globally by vitepress-openapi via OpenAPITheme.enhanceApp -->
<OAOperation :operationId="params.operationId" :prefix-headings="true" />
