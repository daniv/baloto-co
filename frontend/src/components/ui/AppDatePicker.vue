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

const monthLabel = computed(() => {
  const label = viewDate.value.toLocaleDateString('es-CO', { month: 'long', year: 'numeric' })
  return `${label[0].toUpperCase()}${label.slice(1)}`
})

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

const showYearPicker = ref(false)

const availableYears = computed(() => {
  if (props.allowedDates.length === 0) return []
  const years = new Set(props.allowedDates.map((d: string) => isoParts(d)[0]))
  return [...years].sort((a, b) => a - b)
})

const yearRangeLabel = computed(() => {
  if (availableYears.value.length === 0) return ''
  const [min, max] = [availableYears.value[0], availableYears.value.at(-1)!]
  return min === max ? `${min}` : `${min} – ${max}`
})

function selectYear(year: number) {
  viewDate.value = new Date(year, viewDate.value.getMonth(), 1)
  showYearPicker.value = false
}

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
      class="absolute z-20 mt-2 w-64 rounded-xl border border-slate-200 bg-white p-3 shadow-lg dark:border-slate-700 dark:bg-slate-900"
    >
      <template v-if="!showYearPicker">
        <div class="mb-2 flex items-center justify-between">
          <button
            type="button"
            class="rounded-md p-1 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
            aria-label="Mes anterior"
            @click="previousMonth"
          >
            ‹
          </button>
          <span class="text-sm font-medium text-slate-900 dark:text-white">
            {{ monthLabel.split(' ')[0] }}
            <button
              type="button"
              class="ml-1 rounded px-1 text-slate-400 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-500 dark:hover:bg-slate-800 dark:hover:text-white"
              @click="showYearPicker = true"
            >
              {{ viewDate.getFullYear() }}
            </button>
          </span>
          <button
            type="button"
            class="rounded-md p-1 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
            aria-label="Mes siguiente"
            @click="nextMonth"
          >
            ›
          </button>
        </div>

        <div class="grid grid-cols-7 gap-1 text-center text-xs text-slate-400 dark:text-slate-500">
          <span v-for="label in ['L', 'M', 'M', 'J', 'V', 'S', 'D']" :key="label">{{ label }}</span>
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
      </template>

      <template v-else>
        <div class="mb-2 flex items-center justify-between">
          <span class="text-sm font-medium text-slate-900 dark:text-white">{{ yearRangeLabel }}</span>
          <button
            type="button"
            class="rounded-md p-1 text-xs text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
            @click="showYearPicker = false"
          >
            ✕
          </button>
        </div>
        <div class="grid max-h-48 grid-cols-3 gap-1 overflow-y-auto">
          <button
            v-for="year in availableYears"
            :key="year"
            type="button"
            class="rounded-lg px-2 py-1.5 text-center text-sm text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
            :class="{ 'bg-brand-600 text-white hover:bg-brand-600': year === viewDate.getFullYear() }"
            @click="selectYear(year)"
          >
            {{ year }}
          </button>
        </div>
      </template>
    </div>
  </div>
</template>
