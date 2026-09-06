<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps<{ modelValue: string | null; allowedDates: string[] }>()
const emit = defineEmits<{ 'update:modelValue': [string | null] }>()

const root = ref<HTMLElement | null>(null)
const open = ref(false)
const allowedSet = computed(() => new Set(props.allowedDates))
const latestAllowed = computed(() => props.allowedDates.at(-1) ?? null)

function isoParts(iso: string): [number, number, number] {
  const [y, m, d] = iso.split('-').map(Number)
  return [y, m, d]
}

function toIso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function monthFrom(iso: string): Date {
  const [y, m] = isoParts(iso)
  return new Date(y, m - 1, 1)
}

const viewDate = ref(monthFrom(props.modelValue ?? latestAllowed.value ?? toIso(new Date())))

watch(
  () => props.modelValue,
  (value: string | null) => {
    if (value) viewDate.value = monthFrom(value)
  },
)

watch(latestAllowed, (value: string | null) => {
  if (!props.modelValue && value) viewDate.value = monthFrom(value)
})

const monthNames = [
  'Enero',
  'Febrero',
  'Marzo',
  'Abril',
  'Mayo',
  'Junio',
  'Julio',
  'Agosto',
  'Septiembre',
  'Octubre',
  'Noviembre',
  'Diciembre',
]

const weekdayLabels = ['L', 'M', 'X', 'J', 'V', 'S', 'D']

const weeks = computed(() => {
  const year = viewDate.value.getFullYear()
  const month = viewDate.value.getMonth()
  const firstDay = new Date(year, month, 1)
  const startOffset = (firstDay.getDay() + 6) % 7
  const daysInMonth = new Date(year, month + 1, 0).getDate()

  const cells: (Date | null)[] = Array.from({ length: startOffset }, () => null)
  for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(year, month, d))
  while (cells.length % 7 !== 0) cells.push(null)

  const result: (Date | null)[][] = []
  for (let i = 0; i < cells.length; i += 7) result.push(cells.slice(i, i + 7))
  return result
})

function isAllowed(day: Date | null): boolean {
  return day !== null && allowedSet.value.has(toIso(day))
}

function isSelected(day: Date | null): boolean {
  return day !== null && props.modelValue === toIso(day)
}

function selectDay(day: Date | null) {
  if (!isAllowed(day) || day === null) return
  emit('update:modelValue', toIso(day))
  open.value = false
}

function previousMonth() {
  viewDate.value = new Date(viewDate.value.getFullYear(), viewDate.value.getMonth() - 1, 1)
}

function nextMonth() {
  viewDate.value = new Date(viewDate.value.getFullYear(), viewDate.value.getMonth() + 1, 1)
}

const availableYears = computed(() => {
  const years = new Set(props.allowedDates.map((d: string) => isoParts(d)[0]))
  years.add(viewDate.value.getFullYear())
  return [...years].sort((a, b) => a - b)
})

const selectedMonth = computed({
  get: () => viewDate.value.getMonth(),
  set: (month: number) => {
    viewDate.value = new Date(viewDate.value.getFullYear(), month, 1)
  },
})

const selectedYear = computed({
  get: () => viewDate.value.getFullYear(),
  set: (year: number) => {
    viewDate.value = new Date(year, viewDate.value.getMonth(), 1)
  },
})

const displayLabel = computed(() => {
  if (!props.modelValue) return 'Selecciona una fecha'
  const [y, m, d] = isoParts(props.modelValue)
  const formatted = new Date(y, m - 1, d).toLocaleDateString('es-CO', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  })
  return formatted.replace(/de ([a-zé]+)/, (_match, month: string) => `de ${month[0].toUpperCase()}${month.slice(1)}`)
})

function handleOutsideClick(event: MouseEvent) {
  if (root.value && !root.value.contains(event.target as Node)) open.value = false
}

onMounted(() => document.addEventListener('click', handleOutsideClick))
onBeforeUnmount(() => document.removeEventListener('click', handleOutsideClick))
</script>

<template>
  <div ref="root" class="relative">
    <button
      type="button"
      class="flex w-56 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-left text-sm text-slate-700 transition-colors hover:border-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-slate-600"
      @click="open = !open"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.75"
        class="h-4 w-4 shrink-0 text-slate-400"
      >
        <rect x="3.5" y="5" width="17" height="16" rx="2" />
        <path stroke-linecap="round" d="M8 3v4M16 3v4M3.5 10h17" />
      </svg>
      <span class="truncate">{{ displayLabel }}</span>
    </button>

    <div
      v-if="open"
      class="absolute z-20 mt-2 w-72 rounded-xl border border-slate-200 bg-white p-3 shadow-lg dark:border-slate-700 dark:bg-slate-900"
      @click.stop
    >
      <div class="mb-3 flex items-center gap-1.5">
        <button
          type="button"
          class="shrink-0 rounded-md p-1.5 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
          aria-label="Mes anterior"
          @click="previousMonth"
        >
          ‹
        </button>

        <select
          v-model.number="selectedMonth"
          aria-label="Mes"
          class="min-w-0 flex-1 cursor-pointer rounded-md border border-slate-200 bg-white py-1 text-center text-sm font-medium text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-white"
        >
          <option v-for="(name, i) in monthNames" :key="i" :value="i">{{ name }}</option>
        </select>

        <select
          v-model.number="selectedYear"
          aria-label="Año"
          class="w-20 shrink-0 cursor-pointer rounded-md border border-slate-200 bg-white py-1 text-center text-sm font-medium text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-white"
        >
          <option v-for="year in availableYears" :key="year" :value="year">{{ year }}</option>
        </select>

        <button
          type="button"
          class="shrink-0 rounded-md p-1.5 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
          aria-label="Mes siguiente"
          @click="nextMonth"
        >
          ›
        </button>
      </div>

      <div class="grid grid-cols-7 gap-1 text-center text-xs text-slate-400 dark:text-slate-500">
        <span v-for="(label, i) in weekdayLabels" :key="i">{{ label }}</span>
      </div>

      <div v-for="(week, wi) in weeks" :key="wi" class="grid grid-cols-7 gap-1">
        <button
          v-for="(day, di) in week"
          :key="di"
          type="button"
          class="flex h-8 w-8 items-center justify-center rounded-full text-sm text-slate-700 disabled:cursor-not-allowed disabled:text-slate-300 dark:text-slate-200 dark:disabled:text-slate-700"
          :class="{
            'hover:bg-slate-100 dark:hover:bg-slate-800': isAllowed(day) && !isSelected(day),
            'bg-brand-600 text-white hover:bg-brand-600': isSelected(day),
          }"
          :disabled="!isAllowed(day)"
          @click="selectDay(day)"
        >
          {{ day?.getDate() ?? '' }}
        </button>
      </div>
    </div>
  </div>
</template>
