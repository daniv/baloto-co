import { apiGet } from '@/lib/http'
import type { PaginatedResponse } from '@/types/api'
import type { MilotoDraw, MilotoDrawListItem } from '@/types/miloto'

/**
 * List Miloto draws for the results table, newest first.
 *
 * @param page - 1-indexed page number.
 * @param size - Page size.
 * @param gameDate - Restrict to a single draw date, if given.
 * @param jackpot - Restrict to draws that did or didn't hit the jackpot, if given.
 * @returns The matching page of draws.
 */
export function getMilotoDraws(
  page: number,
  size = 10,
  gameDate?: string | null,
  jackpot?: boolean | null,
): Promise<PaginatedResponse<MilotoDrawListItem>> {
  const params: Record<string, string | number> = { page, size }
  if (gameDate) params.game_date = gameDate
  if (jackpot != null) params.jackpot = jackpot ? 'true' : 'false'
  return apiGet<PaginatedResponse<MilotoDrawListItem>>('/miloto/draws', params)
}

/** List every date a Miloto draw was held, for restricting a date-picker to valid dates. */
export function getMilotoDrawDates(): Promise<string[]> {
  return apiGet<string[]>('/miloto/draws/dates')
}

/**
 * Fetch a single Miloto draw's full detail, including prize tiers.
 *
 * @param gameId - The draw's id.
 * @returns The draw's detail.
 */
export function getMilotoDraw(gameId: number): Promise<MilotoDraw> {
  return apiGet<MilotoDraw>(`/miloto/draw/${gameId}`)
}
