import { z } from "zod"

const REQUEST_TIMEOUT_MS = 10_000
const BUILD_TIMEOUT_MS = 60_000

const ModelSummary = z.object({ id: z.string(), name: z.string(), error: z.string().optional() })
const ParamSpec = z.object({
  key: z.string(),
  label: z.string(),
  min: z.number(),
  max: z.number(),
  step: z.number(),
  default: z.number(),
})
const ParamValues = z.record(z.string(), z.number())
const Stats = z.record(z.string(), z.string())
const ModelSchema = z.object({ name: z.string(), params: z.array(ParamSpec), values: ParamValues, stats: Stats, version: z.number() })
const BuildResponse = z.union([
  z.object({ ok: z.literal(true), version: z.number(), values: ParamValues, stats: Stats, builtAt: z.string() }),
  z.object({ ok: z.literal(false), superseded: z.literal(true) }),
  z.object({ ok: z.literal(false), error: z.string() }),
])
const VersionResponse = z.object({ version: z.number() })
const ErrorResponse = z.object({ error: z.string() })

export type ModelSummary = z.infer<typeof ModelSummary>
export type ParamSpec = z.infer<typeof ParamSpec>
export type ParamValues = z.infer<typeof ParamValues>
export type Stats = z.infer<typeof Stats>
export type ModelSchema = z.infer<typeof ModelSchema>
export type BuildResponse = z.infer<typeof BuildResponse>
export type Mesh = { data: ArrayBuffer; version: number }

export type Result<T> = { ok: true; value: T } | { ok: false; error: string }

function withTimeout(timeoutMs: number, signal?: AbortSignal): AbortSignal {
  const timeout = AbortSignal.timeout(timeoutMs)
  return signal ? AbortSignal.any([signal, timeout]) : timeout
}

function describe(error: unknown): string {
  if (error instanceof DOMException && error.name === "TimeoutError") return "the preview server did not answer in time"
  if (error instanceof TypeError) return "the preview server is not running"
  return error instanceof Error ? error.message : String(error)
}

async function request(url: string, init: RequestInit, timeoutMs: number, signal?: AbortSignal): Promise<Result<Response>> {
  try {
    const response = await fetch(url, { ...init, signal: withTimeout(timeoutMs, signal) })
    if (response.ok) return { ok: true, value: response }
    const body = ErrorResponse.safeParse(await response.json().catch(() => null))
    return { ok: false, error: body.success ? body.data.error : `the server answered ${response.status}` }
  } catch (error) {
    return { ok: false, error: describe(error) }
  }
}

async function requestJson<T>(url: string, schema: z.ZodType<T>, init: RequestInit = {}, timeoutMs = REQUEST_TIMEOUT_MS, signal?: AbortSignal): Promise<Result<T>> {
  const response = await request(url, init, timeoutMs, signal)
  if (!response.ok) return response
  try {
    const parsed = schema.safeParse(await response.value.json())
    return parsed.success ? { ok: true, value: parsed.data } : { ok: false, error: `unexpected answer from ${url}` }
  } catch (error) {
    return { ok: false, error: describe(error) }
  }
}

export function listModels(): Promise<Result<ModelSummary[]>> {
  return requestJson("/api/models", z.array(ModelSummary))
}

export function getModelSchema(modelId: string, signal?: AbortSignal): Promise<Result<ModelSchema>> {
  return requestJson(`/api/schema?model=${encodeURIComponent(modelId)}`, ModelSchema, {}, REQUEST_TIMEOUT_MS, signal)
}

export function buildModel(modelId: string, values: ParamValues, signal: AbortSignal): Promise<Result<BuildResponse>> {
  const init = { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model: modelId, values }) }
  return requestJson("/api/build", BuildResponse, init, BUILD_TIMEOUT_MS, signal)
}

export async function getMeshVersion(modelId: string): Promise<Result<number>> {
  const result = await requestJson(`/api/version?model=${encodeURIComponent(modelId)}`, VersionResponse)
  return result.ok ? { ok: true, value: result.value.version } : result
}

export async function getMesh(modelId: string, signal?: AbortSignal): Promise<Result<Mesh>> {
  const response = await request(`/api/mesh?model=${encodeURIComponent(modelId)}`, {}, REQUEST_TIMEOUT_MS, signal)
  if (!response.ok) return response
  try {
    const version = Number(response.value.headers.get("X-Mesh-Version"))
    return { ok: true, value: { data: await response.value.arrayBuffer(), version } }
  } catch (error) {
    return { ok: false, error: describe(error) }
  }
}
