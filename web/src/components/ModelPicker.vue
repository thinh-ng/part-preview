<script setup lang="ts">
import { useId } from "vue"
import type { ModelSummary } from "@/lib/api"

const { models } = defineProps<{ models: ModelSummary[] }>()
const selected = defineModel<string | null>({ required: true })
const id = useId()
</script>

<template>
  <div class="model-picker">
    <label :for="id">Model</label>
    <select :id="id" v-model="selected" class="model-select">
      <option :value="null" disabled>Choose a model</option>
      <option v-for="model in models" :key="model.id" :value="model.id" :disabled="Boolean(model.error)">
        {{ model.error ? `${model.name} (failed to load)` : model.name }}
      </option>
    </select>
  </div>
</template>

<style scoped>
.model-picker { display: grid; gap: var(--space-1); }
.model-select { font: inherit; }
</style>
