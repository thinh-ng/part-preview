<script setup lang="ts">
import { useId } from "vue"
import type { ParamSpec, ParamValues } from "@/lib/api"

const { params, values } = defineProps<{ params: ParamSpec[]; values: ParamValues }>()
const emit = defineEmits<{ change: [values: ParamValues] }>()
const idPrefix = useId()

function onInput(key: string, event: Event): void {
  const target = event.target
  if (target instanceof HTMLInputElement || target instanceof HTMLSelectElement) {
    emit("change", { ...values, [key]: Number(target.value) })
  }
}

function formatted(key: string): string {
  return (values[key] ?? 0).toFixed(2)
}
</script>

<template>
  <fieldset class="param-sliders">
    <legend class="visually-hidden">Parameters</legend>
    <div v-for="param in params" :key="param.key" class="param-row">
      <label class="param-label" :for="`${idPrefix}-${param.key}`">{{ param.label }}</label>
      <select
        v-if="param.options"
        :id="`${idPrefix}-${param.key}`"
        class="param-select"
        :value="Math.round(values[param.key] ?? param.default)"
        @change="onInput(param.key, $event)"
      >
        <option v-for="(name, index) in param.options" :key="index" :value="index">{{ name }}</option>
      </select>
      <template v-else>
        <input
          :id="`${idPrefix}-${param.key}`"
          class="param-input"
          type="range"
          :min="param.min"
          :max="param.max"
          :step="param.step"
          :value="values[param.key]"
          @input="onInput(param.key, $event)"
        />
        <output class="param-value" :for="`${idPrefix}-${param.key}`">{{ formatted(param.key) }}</output>
      </template>
    </div>
  </fieldset>
</template>

<style scoped>
.param-sliders { border: 0; margin: 0; padding: 0; display: grid; gap: var(--space-2); }
.param-row { display: grid; grid-template-columns: 1fr 4rem; gap: var(--space-1) var(--space-2); align-items: center; }
.param-label { grid-column: 1 / 3; }
.param-input { inline-size: 100%; }
.param-select { grid-column: 1 / 3; inline-size: 100%; font: inherit; padding: var(--space-1); }
.param-value { text-align: end; font-variant-numeric: tabular-nums; }
</style>
