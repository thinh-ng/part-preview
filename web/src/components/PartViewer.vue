<script setup lang="ts">
import { onMounted, onUnmounted, useTemplateRef, watch } from "vue"
import { createPartScene } from "@/lib/part-scene"
import type { PartScene } from "@/lib/part-scene"
import type { MeshSource } from "@/lib/mesh-source"

const { mesh, cut, seeThrough } = defineProps<{ mesh: MeshSource | null; cut: number; seeThrough: boolean }>()
const emit = defineEmits<{ error: [message: string] }>()
const container = useTemplateRef<HTMLDivElement>("container")
let partScene: PartScene | null = null

function show(source: MeshSource | null): void {
  if (!source || !partScene) return
  const result = partScene.show(source)
  if (!result.ok) emit("error", result.error)
}

onMounted(() => {
  if (!container.value) return
  partScene = createPartScene(container.value)
  partScene.setCut(cut)
  partScene.setSeeThrough(seeThrough)
  show(mesh)
})
onUnmounted(() => partScene?.dispose())

watch(() => mesh, show)
watch(() => cut, value => partScene?.setCut(value))
watch(() => seeThrough, value => partScene?.setSeeThrough(value))
</script>

<template>
  <div
    ref="container"
    class="part-viewer"
    role="img"
    aria-label="3D view of the part. Drag to rotate, right-drag to pan, scroll to zoom."
  />
</template>

<style scoped>
.part-viewer { position: fixed; inset: 0; }
</style>
