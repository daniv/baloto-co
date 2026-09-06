const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/**
 * Fetch JSON from the backend API, throwing {@link ApiError} on a non-2xx response.
 *
 * @param path - API path relative to the base URL, e.g. "/miloto/draws".
 * @param params - Query string parameters to append.
 * @returns The parsed JSON response body.
 */
export async function apiGet<T>(path: string, params?: Record<string, string | number>): Promise<T> {
  const url = new URL(`${API_BASE_URL}${path}`, window.location.origin)
  for (const [key, value] of Object.entries(params ?? {})) {
    url.searchParams.set(key, String(value))
  }

  const response = await fetch(url, { headers: { Accept: 'application/json' } })

  if (!response.ok) {
    throw new ApiError(response.status, `Request to ${path} failed with status ${response.status}`)
  }

  return (await response.json()) as T
}
