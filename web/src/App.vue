<script setup lang="ts">
import { computed, onMounted, ref, shallowRef, watch } from "vue"
import ModelPicker from "@/components/ModelPicker.vue"
import ParamSliders from "@/components/ParamSliders.vue"
import PartViewer from "@/components/PartViewer.vue"
import StatsList from "@/components/StatsList.vue"
import { usePartModel } from "@/composables/usePartModel"
import { listModels } from "@/lib/api"
import type { ModelSummary } from "@/lib/api"
import { formatFromFileName } from "@/lib/mesh-source"
import type { MeshSource } from "@/lib/mesh-source"

const STORAGE_KEY = "part-preview-model"
const NARROW_SCREEN = "(max-width: 40rem)"   // keep in step with the @media rule below

const models = ref<ModelSummary[]>([])
const modelsLoaded = ref(false)
const pageError = ref("")
const selectedId = ref<string | null>(null)
const droppedMesh = shallowRef<MeshSource | null>(null)
const droppedName = ref("")
const dragDepth = ref(0)
const cut = ref(1)
const seeThrough = ref(false)
// On a phone the panel starts closed so the part is visible; on a wide screen it starts open.
const panelOpen = ref(!window.matchMedia(NARROW_SCREEN).matches)

const { schema, values, stats, error, builtAt, mesh, updateValues, resetToDefaults, reload } = usePartModel(selectedId)

const editedSchema = computed(() => (droppedMesh.value === null ? schema.value : null))
const shownMesh = computed(() => droppedMesh.value ?? mesh.value)
const shownError = computed(() => pageError.value || error.value)
const isDragging = computed(() => dragDepth.value > 0)
// Errors live in the panel; a closed panel would leave an empty view with no reason given.
watch(shownError, message => {
  if (message) panelOpen.value = true
})
const status = computed(() => {
  if (droppedName.value) return `Viewing ${droppedName.value}. Pick a model to go back to the sliders.`
  if (modelsLoaded.value && models.value.length === 0) return "No models in models/. Drop an STL or 3MF file to view it."
  if (builtAt.value) return `Built at ${builtAt.value}`
  return schema.value ? "Ready" : "Loading..."
})

function readStoredModel(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch (storageError) {
    console.warn("model choice not restored:", storageError)
    return null
  }
}

watch(selectedId, id => {
  if (!id) return
  droppedMesh.value = null
  droppedName.value = ""
  pageError.value = ""
  try {
    localStorage.setItem(STORAGE_KEY, id)
  } catch (storageError) {
    console.warn("model choice not remembered:", storageError)
  }
})

async function loadModels(): Promise<void> {
  pageError.value = ""
  const result = await listModels()
  if (!result.ok) {
    pageError.value = `Could not list models: ${result.error}`
    return
  }
  models.value = result.value
  modelsLoaded.value = true
  const usable = result.value.filter(model => !model.error)
  const stored = readStoredModel()
  selectedId.value = usable.find(model => model.id === stored)?.id ?? usable[0]?.id ?? null
}

function retry(): void {
  if (modelsLoaded.value) reload()
  else void loadModels()
}

function onDragEnter(event: DragEvent): void {
  if (event.dataTransfer?.types.includes("Files")) dragDepth.value += 1
}

function onDragLeave(): void {
  dragDepth.value = Math.max(dragDepth.value - 1, 0)
}

async function onDrop(event: DragEvent): Promise<void> {
  dragDepth.value = 0
  const file = event.dataTransfer?.files[0]
  if (!file) return
  const format = formatFromFileName(file.name)
  if (!format) {
    pageError.value = "Only STL and 3MF files can be viewed."
    return
  }
  pageError.value = ""
  droppedMesh.value = { format, data: await file.arrayBuffer(), reframe: true }
  droppedName.value = file.name
  selectedId.value = null
}

onMounted(() => void loadModels())
</script>

<template>
  <main
    class="app"
    :class="{ 'panel-open': panelOpen }"
    @dragenter.prevent="onDragEnter"
    @dragover.prevent
    @dragleave="onDragLeave"
    @drop.prevent="onDrop"
  >
    <PartViewer :mesh="shownMesh" :cut="cut" :see-through="seeThrough" @error="pageError = $event" />

    <button class="panel-toggle" type="button" aria-controls="panel" :aria-expanded="panelOpen" @click="panelOpen = !panelOpen">
      {{ panelOpen ? "Hide settings" : "Settings" }}
    </button>

    <aside v-show="panelOpen" id="panel" class="panel" aria-labelledby="panel-title">
      <h1 id="panel-title" class="panel-title">Part preview</h1>
      <ModelPicker v-model="selectedId" :models="models" />
      <template v-if="editedSchema">
        <ParamSliders :params="editedSchema.params" :values="values" @change="updateValues" />
        <StatsList :stats="stats" />
        <button class="panel-button" type="button" @click="resetToDefaults">Reset to defaults</button>
      </template>
      <div class="panel-error" role="alert">
        <template v-if="shownError">
          <span>{{ shownError }}</span>
          <button class="panel-button" type="button" @click="retry">Retry</button>
        </template>
      </div>
      <hr class="panel-rule" />
      <label class="panel-row">
        Cut
        <input v-model.number="cut" class="panel-range" type="range" min="0" max="1" step="0.001" />
      </label>
      <label class="panel-row"><input v-model="seeThrough" type="checkbox" /> See-through</label>
      <p class="panel-hint" aria-live="polite">{{ status }}</p>
      <p class="panel-hint">
        Drag to rotate, right-drag or two-finger drag to pan, scroll or pinch to zoom. Drop an STL or 3MF file on the page to view it.
      </p>
    </aside>

    <div v-if="isDragging" class="drop-overlay">Drop STL or 3MF to view</div>
  </main>
</template>

<style scoped>
.panel-toggle { position: fixed; inset-block-start: var(--space-3); inset-inline-start: var(--space-3); z-index: 1;
                font: inherit; padding: var(--space-2) var(--space-3); background: var(--color-panel); color: var(--color-text);
                border: 1px solid var(--color-line); border-radius: var(--radius); }
.panel { position: fixed; inset-block-start: calc(var(--space-3) * 2 + 2.5rem); inset-inline-start: var(--space-3);
         inline-size: min(22rem, calc(100vw - 2 * var(--space-3)));
         max-block-size: calc(100vh - var(--space-3) * 3 - 2.5rem);
         overflow: auto; display: grid; gap: var(--space-2); background: var(--color-panel);
         border: 1px solid var(--color-line); border-radius: var(--radius); padding: var(--space-3); }
.panel-title { font-size: var(--font-size-title); margin: 0; }
.panel-row { display: flex; gap: var(--space-2); align-items: center; }
.panel-range { flex: 1; }
.panel-hint { color: var(--color-muted); font-size: var(--font-size-small); margin: 0; }
.panel-error { color: var(--color-error); font-size: var(--font-size-small); display: grid; gap: var(--space-1); }
.panel-error:empty { display: none; }
.panel-rule { border: 0; border-block-start: 1px solid var(--color-line); inline-size: 100%; margin: 0; }
.panel-button { font: inherit; justify-self: start; }
/* Phone: the panel docks to the bottom half and the part shrinks into the top half. */
@media (max-width: 40rem) {
  .app.panel-open { --viewer-bottom: 50dvh; }
  .panel { inset: auto 0 0 0; inline-size: auto; block-size: 50dvh; max-block-size: none;
           border-radius: var(--radius) var(--radius) 0 0; border-inline: 0; border-block-end: 0; }
  .panel-toggle { inset-block-start: auto; inset-inline-start: auto; inset-inline-end: var(--space-3);
                  inset-block-end: calc(var(--space-3) + env(safe-area-inset-bottom)); }
  .app.panel-open .panel-toggle { inset-block-end: calc(50dvh + var(--space-2)); }
}
.drop-overlay { position: fixed; inset: 0; display: grid; place-items: center; pointer-events: none;
                background: var(--color-overlay); color: var(--color-on-overlay); font-size: var(--font-size-title); }
</style>
