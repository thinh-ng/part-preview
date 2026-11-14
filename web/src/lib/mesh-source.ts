export type MeshFormat = "stl" | "3mf"

/** A mesh file for the viewer. `reframe` moves the camera to fit it; otherwise the camera stays put. */
export type MeshSource = { format: MeshFormat; data: ArrayBuffer; reframe: boolean }

export function formatFromFileName(name: string): MeshFormat | null {
  const extension = name.split(".").pop()?.toLowerCase()
  return extension === "stl" || extension === "3mf" ? extension : null
}
