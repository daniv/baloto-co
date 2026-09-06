const pesosFormatter = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  maximumFractionDigits: 0,
})

/**
 * Format an integer amount of Colombian pesos as a localized currency string.
 *
 * @param value - Amount in whole pesos.
 * @returns The formatted amount, e.g. "$ 3.200.000.000".
 */
export function formatPesos(value: number): string {
  return pesosFormatter.format(value)
}

const dateFormatter = new Intl.DateTimeFormat('es-CO', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  year: 'numeric',
})

/**
 * Format an ISO date string as a long-form Spanish date.
 *
 * @param isoDate - Date in "YYYY-MM-DD" form.
 * @returns The formatted date, e.g. "Sábado, 5 de septiembre de 2026".
 */
export function formatSpanishDate(isoDate: string): string {
  const [year, month, day] = isoDate.split('-').map(Number)
  const formatted = dateFormatter.format(new Date(year, month - 1, day))
  return formatted.charAt(0).toUpperCase() + formatted.slice(1)
}
