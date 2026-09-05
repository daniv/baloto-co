<script setup lang="ts">
import { getMilotoDraw } from '@/api/miloto'
import NumberBall from '@/components/ui/NumberBall.vue'
import { ApiError } from '@/lib/http'
import { formatPesos, formatSpanishDate } from '@/lib/format'
import type { MilotoDraw } from '@/types/miloto'
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const draw = ref<MilotoDraw | null>(null)
const loading = ref(false)
const notFound = ref(false)
const error = ref<string | null>(null)

const drawId = computed(() => Number(route.params.id))

async function fetchDraw() {
  loading.value = true
  error.value = null
  notFound.value = false
  draw.value = null
  try {
    draw.value = await getMilotoDraw(drawId.value)
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      notFound.value = true
    } else {
      error.value = 'No se pudo cargar el sorteo. Intenta de nuevo.'
    }
  } finally {
    loading.value = false
  }
}

watch(drawId, fetchDraw, { immediate: true })

const jackpotWon = computed(() => (draw.value?.hits_5?.winners ?? 0) > 0)

const tiers = computed(() => {
  if (!draw.value) return []
  const d = draw.value
  return [
    { hits: 5, label: '5 aciertos', highlight: 'Premio mayor', details: d.hits_5 },
    { hits: 4, label: '4 aciertos', highlight: null, details: d.hits_4 },
    { hits: 3, label: '3 aciertos', highlight: null, details: d.hits_3 },
    { hits: 2, label: '2 aciertos', highlight: null, details: d.hits_2 },
  ]
})
</script>

<template>
  <div>
    <div v-if="loading" class="py-16 text-center text-slate-400 dark:text-slate-500">Cargando…</div>

    <div v-else-if="notFound" class="py-16 text-center">
      <p class="text-lg font-medium text-slate-900 dark:text-white">No encontramos este sorteo</p>
      <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
        No hay un sorteo Miloto #{{ route.params.id }} guardado.
      </p>
    </div>

    <div v-else-if="error" class="py-16 text-center text-red-500">{{ error }}</div>

    <template v-else-if="draw">
      <div class="mb-6">
        <h1 class="text-2xl font-semibold tracking-tight text-slate-900 dark:text-white">
          Sorteo Miloto #{{ draw.game_id }}
        </h1>
        <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">{{ formatSpanishDate(draw.game_date) }}</p>
      </div>

      <div class="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
        <p class="text-xs font-medium text-slate-500 dark:text-slate-400">Números ganadores</p>
        <div class="mt-3 flex flex-wrap gap-3">
          <NumberBall v-for="n in draw.numbers" :key="n" :value="n" size="lg" :accent="jackpotWon" />
        </div>

        <div
          class="mt-6 flex flex-wrap items-end justify-between gap-4 border-t border-slate-100 pt-5 dark:border-slate-800"
        >
          <div>
            <p class="text-xs font-medium text-slate-500 dark:text-slate-400">Acumulado</p>
            <p class="mt-1 text-2xl font-semibold tabular-nums text-slate-900 dark:text-white">
              {{ formatPesos(draw.accumulated) }}
            </p>
          </div>
          <span
            v-if="jackpotWon"
            class="inline-flex items-center rounded-full bg-amber-50 px-3 py-1 text-sm font-medium text-amber-700 dark:bg-amber-500/10 dark:text-amber-400"
          >
            Se ganó el premio mayor
          </span>
          <span
            v-else
            class="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400"
          >
            Nadie acertó las 5, el acumulado sigue creciendo
          </span>
        </div>
      </div>

      <div class="mt-6">
        <h2 class="mb-3 text-sm font-semibold text-slate-900 dark:text-white">Premios por acierto</h2>
        <ul
          class="divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200 bg-white dark:divide-slate-800 dark:border-slate-800 dark:bg-slate-900"
        >
          <li v-for="tier in tiers" :key="tier.hits" class="flex flex-wrap items-center gap-x-6 gap-y-2 px-5 py-4">
            <div class="flex items-center gap-3">
              <div class="flex gap-1" aria-hidden="true">
                <span
                  v-for="i in 5"
                  :key="i"
                  class="h-2 w-2 rounded-full"
                  :class="
                    i <= tier.hits
                      ? tier.hits === 5 && jackpotWon
                        ? 'bg-amber-500'
                        : 'bg-brand-500'
                      : 'bg-slate-200 dark:bg-slate-700'
                  "
                />
              </div>
              <div>
                <p class="text-sm font-medium text-slate-900 dark:text-white">{{ tier.label }}</p>
                <p v-if="tier.highlight" class="text-xs text-slate-500 dark:text-slate-400">{{ tier.highlight }}</p>
              </div>
            </div>

            <div class="ml-auto text-right">
              <template v-if="tier.details && tier.details.winners > 0">
                <p class="text-sm tabular-nums text-slate-900 dark:text-white">
                  {{ tier.details.winners.toLocaleString('es-CO') }} ganadores
                </p>
                <p class="text-xs tabular-nums text-slate-500 dark:text-slate-400">
                  {{ formatPesos(tier.details.prize_for_winner) }} c/u
                </p>
              </template>
              <p v-else class="text-sm text-slate-400 dark:text-slate-500">Sin ganadores</p>
            </div>
          </li>
        </ul>
      </div>
    </template>
  </div>
</template>
