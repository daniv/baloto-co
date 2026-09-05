import { apiGet } from '@/lib/http'
import type { PaginatedResponse } from '@/types/api'
import type { MilotoDrawListItem } from '@/types/miloto'

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

export function getMilotoDrawDates(): Promise<string[]> {
  return apiGet<string[]>('/miloto/draws/dates')
}
