export interface PaginatedResponse<T> {
  items: T[]
  page: number
  size: number
  total: number
  pages: number
}
