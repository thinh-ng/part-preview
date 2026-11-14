<script setup lang="ts">
import type { Stats } from "@/lib/api"

const { stats } = defineProps<{ stats: Stats }>()
</script>

<template>
  <dl class="stats-list">
    <template v-for="(value, label) in stats" :key="label">
      <dt class="stats-label">{{ label }}</dt>
      <dd class="stats-value">{{ value }}</dd>
    </template>
  </dl>
</template>

<style scoped>
.stats-list { display: grid; grid-template-columns: auto auto; gap: 0 var(--space-3); margin: 0;
              font: var(--font-size-small) / 1.5 var(--font-mono); }
.stats-label { color: var(--color-muted); }
.stats-value { margin: 0; text-align: end; }
</style>
