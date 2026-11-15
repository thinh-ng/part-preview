import * as THREE from "three"
import { OrbitControls } from "three/addons/controls/OrbitControls.js"
import { STLLoader } from "three/addons/loaders/STLLoader.js"
import { ThreeMFLoader } from "three/addons/loaders/3MFLoader.js"
import type { Result } from "@/lib/api"
import type { MeshSource } from "@/lib/mesh-source"

export type PartScene = {
  show: (source: MeshSource) => Result<null>
  setCut: (fraction: number) => void
  setSeeThrough: (enabled: boolean) => void
  dispose: () => void
}

const SEE_THROUGH_OPACITY = 0.45
// Outline creases sharper than this; lower values also outline curved surfaces facet by facet.
const EDGE_ANGLE_DEGREES = 30
const FRAME_MARGIN = 1.05

function cssColor(name: string): THREE.Color {
  return new THREE.Color(getComputedStyle(document.documentElement).getPropertyValue(name).trim())
}

function disposeMaterial(material: THREE.Material | THREE.Material[], keep: THREE.Material): void {
  for (const item of Array.isArray(material) ? material : [material]) {
    if (item === keep) continue
    if ("map" in item && item.map instanceof THREE.Texture) item.map.dispose()
    item.dispose()
  }
}

/** Three.js view of one part, Z up, with a front-to-back section plane. Renders only when something changes. */
export function createPartScene(container: HTMLElement): PartScene {
  const renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setPixelRatio(window.devicePixelRatio)
  renderer.localClippingEnabled = true
  container.appendChild(renderer.domElement)

  const scene = new THREE.Scene()
  const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 10000)
  camera.up.set(0, 0, 1)
  scene.add(new THREE.HemisphereLight(0xffffff, 0x444444, 1.2))
  const sun = new THREE.DirectionalLight(0xffffff, 1.4)
  scene.add(sun)
  const controls = new OrbitControls(camera, renderer.domElement)

  const clipPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), 0)
  const material = new THREE.MeshStandardMaterial({
    metalness: 0.05,
    roughness: 0.6,
    side: THREE.DoubleSide,
    clippingPlanes: [clipPlane],
  })
  const edgeMaterial = new THREE.LineBasicMaterial({ clippingPlanes: [clipPlane] })
  const bounds = new THREE.Box3()
  let current: THREE.Object3D | null = null
  let cutFraction = 1
  let frameRequested = false

  function render(): void {
    frameRequested = false
    sun.position.copy(camera.position)
    renderer.render(scene, camera)
  }
  function requestRender(): void {
    if (frameRequested) return
    frameRequested = true
    requestAnimationFrame(render)
  }

  function applyColors(): void {
    scene.background = cssColor("--color-bg")
    // Per-triangle colors are multiplied by the material color, so it goes white when they are present.
    material.color = material.vertexColors ? new THREE.Color(0xffffff) : cssColor("--color-part")
    edgeMaterial.color = cssColor("--color-edge")
    requestRender()
  }
  const colorScheme = window.matchMedia("(prefers-color-scheme: dark)")
  colorScheme.addEventListener("change", applyColors)
  applyColors()

  function applyCut(): void {
    clipPlane.constant = bounds.min.y + (bounds.max.y - bounds.min.y) * cutFraction + 0.001
    requestRender()
  }

  function disposeCurrent(): void {
    if (!current) return
    scene.remove(current)
    current.traverse(object => {
      if (object instanceof THREE.Mesh || object instanceof THREE.LineSegments) object.geometry.dispose()
    })
    current = null
  }

  function parse(source: MeshSource): THREE.Object3D {
    if (source.format === "stl") return new THREE.Mesh(new STLLoader().parse(source.data), material)
    return new ThreeMFLoader().parse(source.data)
  }

  function show(source: MeshSource): Result<null> {
    let object: THREE.Object3D
    try {
      object = parse(source)
    } catch (error) {
      return { ok: false, error: `Could not read the file: ${error instanceof Error ? error.message : String(error)}` }
    }
    const nextBounds = new THREE.Box3().setFromObject(object)
    if (nextBounds.isEmpty()) return { ok: false, error: "The file contains no geometry." }
    const meshes: THREE.Mesh[] = []
    object.traverse(child => {
      if (child instanceof THREE.Mesh) meshes.push(child)
    })
    let hasColors = false
    for (const child of meshes) {
      disposeMaterial(child.material, material)
      child.material = material
      child.geometry.computeVertexNormals()
      hasColors ||= "hasColors" in child.geometry && child.geometry.hasColors === true
      child.add(new THREE.LineSegments(new THREE.EdgesGeometry(child.geometry, EDGE_ANGLE_DEGREES), edgeMaterial))
    }
    if (material.vertexColors !== hasColors) {
      material.vertexColors = hasColors
      material.needsUpdate = true
    }
    applyColors()
    disposeCurrent()
    current = object
    scene.add(object)
    bounds.copy(nextBounds)
    if (source.reframe) {
      const center = bounds.getCenter(new THREE.Vector3())
      const radius = bounds.getSize(new THREE.Vector3()).length() / 2
      // Fit the bounding sphere in the narrower of the two fields of view, so a tall phone screen shows the whole part.
      const verticalFov = THREE.MathUtils.degToRad(camera.fov)
      const horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * camera.aspect)
      const distance = (radius / Math.sin(Math.min(verticalFov, horizontalFov) / 2)) * FRAME_MARGIN
      camera.position.copy(center).add(new THREE.Vector3(1, -1, 0.8).normalize().multiplyScalar(distance))
      controls.target.copy(center)
      controls.update()
    }
    applyCut()
    return { ok: true, value: null }
  }

  controls.addEventListener("change", requestRender)
  const resizeObserver = new ResizeObserver(() => {
    const { clientWidth, clientHeight } = container
    renderer.setSize(clientWidth, clientHeight)
    camera.aspect = clientWidth / Math.max(clientHeight, 1)
    camera.updateProjectionMatrix()
    requestRender()
  })
  resizeObserver.observe(container)

  return {
    show,
    setCut(fraction) {
      cutFraction = fraction
      applyCut()
    },
    setSeeThrough(enabled) {
      material.transparent = enabled
      material.opacity = enabled ? SEE_THROUGH_OPACITY : 1
      material.needsUpdate = true
      requestRender()
    },
    dispose() {
      colorScheme.removeEventListener("change", applyColors)
      resizeObserver.disconnect()
      controls.removeEventListener("change", requestRender)
      disposeCurrent()
      material.dispose()
      edgeMaterial.dispose()
      controls.dispose()
      renderer.dispose()
      renderer.domElement.remove()
    },
  }
}
