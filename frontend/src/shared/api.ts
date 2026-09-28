export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public fields: Record<string, string> = {},
  ) {
    super(message)
  }
}

export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  headers.set('Accept', 'application/json')
  if (options.body) headers.set('Content-Type', 'application/json')

  const response = await fetch(path, { ...options, headers })
  const payload: unknown = response.headers.get('content-type')?.includes('application/json')
    ? await response.json()
    : null

  if (!response.ok) {
    const fields: Record<string, string> = {}
    if (payload && typeof payload === 'object' && !Array.isArray(payload)) {
      for (const [key, value] of Object.entries(payload)) {
        if (typeof value === 'string') fields[key] = value
        else if (Array.isArray(value)) fields[key] = value.map(String).join(' ')
      }
    }
    throw new ApiError(
      fields.error || fields.detail || fields.non_field_errors || Object.values(fields)[0] || `通信エラー (${response.status})`,
      response.status,
      fields,
    )
  }
  return payload as T
}