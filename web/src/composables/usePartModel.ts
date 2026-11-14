import { onUnmounted, ref, shallowRef, watch } from "vue"
import type { Ref, ShallowRef } from "vue"
import { buildModel, getMesh, getMeshVersion, getModelSchema } from "@/lib/api"
import type { ModelSchema, ParamValues, Stats } from "@/lib/api"
import type { MeshSource } from "@/lib/mesh-source"

const REBUILD_DELAY_MS = 120
const POLL_INTERVAL_MS = 1500

export type PartModel = {
  schema: ShallowRef<ModelSchema | null>
  values: Ref<ParamValues>
  stats: Ref<Stats>
  error: Ref<string>
  builtAt: Ref<string>
  mesh: ShallowRef<MeshSource | null>
  updateValues: (next: ParamValues) => void
  resetToDefaults: () => void
  reload: () => void
}

/**
 * Loads a parametric model, rebuilds it when the user changes a value, and follows builds made
 * outside the page. Every async step carries the generation it started in; a step from an older
 * generation (another model, or a newer edit) is dropped.
 */
export function usePartModel(modelId: Ref<string | null>): PartModel {
  const schema = shallowRef<ModelSchema | null>(null)
  const values = ref<ParamValues>({})
  const stats = ref<Stats>({})
  const error = ref("")
  const builtAt = ref("")
  const mesh = shallowRef<MeshSource | null>(null)

  let generation = 0
  let controller = new AbortController()
  let rebuildTimer: ReturnType<typeof setTimeout> | undefined
  let isBuilding = false
  let shownVersion = 0
  let reframeNext = true

  function startGeneration(): number {
    controller.abort()
    controller = new AbortController()
    isBuilding = false
    generation += 1
    return generation
  }

  function cancelPendingRebuild(): void {
    clearTimeout(rebuildTimer)
    rebuildTimer = undefined
  }

  async function showMesh(id: string, current: number): Promise<void> {
    const result = await getMesh(id, controller.signal)
    if (current !== generation) return
    if (!result.ok) {
      error.value = `Could not load the part: ${result.error}`
      return
    }
    mesh.value = { format: "stl", data: result.value.data, reframe: reframeNext }
    reframeNext = false
    shownVersion = result.value.version
  }

  async function load(id: string): Promise<void> {
    cancelPendingRebuild()
    const current = startGeneration()
    schema.value = null
    stats.value = {}
    error.value = ""
    shownVersion = 0
    reframeNext = true
    const result = await getModelSchema(id, controller.signal)
    if (current !== generation) return
    if (!result.ok) {
      error.value = `Could not load the model: ${result.error}`
      return
    }
    schema.value = result.value
    values.value = { ...result.value.values }
    stats.value = result.value.stats
    if (result.value.version > 0) await showMesh(id, current)
    else await rebuild(current)
  }

  async function rebuild(current: number): Promise<void> {
    const id = modelId.value
    if (!id || current !== generation) return
    isBuilding = true
    try {
      const result = await buildModel(id, values.value, controller.signal)
      if (current !== generation) return
      if (!result.ok) {
        error.value = `Could not build: ${result.error}`
        return
      }
      const response = result.value
      if (!response.ok) {
        if ("error" in response) error.value = `Can't build this shape: ${response.error}`
        return
      }
      error.value = ""
      stats.value = response.stats
      builtAt.value = response.builtAt
      await showMesh(id, current)
    } finally {
      if (current === generation) isBuilding = false
    }
  }

  function updateValues(next: ParamValues): void {
    values.value = next
    clearTimeout(rebuildTimer)
    rebuildTimer = setTimeout(() => {
      rebuildTimer = undefined
      void rebuild(startGeneration())
    }, REBUILD_DELAY_MS)
  }

  function resetToDefaults(): void {
    if (schema.value) updateValues(Object.fromEntries(schema.value.params.map(param => [param.key, param.default])))
  }

  function reload(): void {
    if (modelId.value) void load(modelId.value)
  }

  watch(modelId, id => {
    if (id) void load(id)
    else {
      cancelPendingRebuild()
      startGeneration()
      schema.value = null
    }
  }, { immediate: true })

  // A script can rebuild the model too: show its result without rebuilding again.
  const poll = setInterval(() => void followExternalBuild(), POLL_INTERVAL_MS)
  async function followExternalBuild(): Promise<void> {
    const id = modelId.value
    if (!id || isBuilding || rebuildTimer !== undefined || shownVersion === 0) return
    const current = generation
    const version = await getMeshVersion(id)
    if (current !== generation || !version.ok || version.value === shownVersion) return
    const latest = await getModelSchema(id, controller.signal)
    if (current !== generation || !latest.ok) return
    values.value = { ...latest.value.values }
    stats.value = latest.value.stats
    await showMesh(id, current)
  }

  onUnmounted(() => {
    clearInterval(poll)
    cancelPendingRebuild()
    startGeneration()
  })

  return { schema, values, stats, error, builtAt, mesh, updateValues, resetToDefaults, reload }
}
