<script setup lang="ts">
import { getMilotoDrawDates, getMilotoDraws } from '@/api/miloto'
import AppDatePicker from '@/components/ui/AppDatePicker.vue'
import AppPagination from '@/components/ui/AppPagination.vue'
import NumberBall from '@/components/ui/NumberBall.vue'
import type { PaginatedResponse } from '@/types/api'
import type { MilotoDrawListItem } from '@/types/miloto'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const result = ref<PaginatedResponse<MilotoDrawListItem> | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const allowedDates = ref<string[]>([])

const pageFromQuery = computed(() => {
  const parsed = Number(route.query.page)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1
})
const dateFromQuery = computed(() => (typeof route.query.date === 'string' ? route.query.date : null))

const searchDate = ref<string | null>(dateFromQuery.value)
watch(dateFromQuery, (value) => (searchDate.value = value))

async function fetchDraws() {
  loading.value = true
  error.value = null
  try {
    result.value = await getMilotoDraws(pageFromQuery.value, 10, dateFromQuery.value)
  } catch {
    error.value = 'No se pudieron cargar los resultados de Miloto. Intenta de nuevo.'
  } finally {
    loading.value = false
  }
}

function goToPage(page: number) {
  const query: Record<string, string> = { page: String(page) }
  if (dateFromQuery.value) query.date = dateFromQuery.value
  router.push({ query })
}

function applySearch() {
  const query: Record<string, string> = { page: '1' }
  if (searchDate.value) query.date = searchDate.value
  router.push({ query })
}

function clearSearch() {
  searchDate.value = null
  router.push({ query: {} })
}

watch([pageFromQuery, dateFromQuery], fetchDraws, { immediate: true })

onMounted(async () => {
  try {
    allowedDates.value = await getMilotoDrawDates()
  } catch {
    allowedDates.value = []
  }
})
</script>

<template>
  <div>
    <div class="mb-6">
      <h1 class="text-2xl font-semibold tracking-tight text-slate-900 dark:text-white">Miloto</h1>
      <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">Historial de sorteos, más reciente primero.</p>
    </div>

    <div class="mb-4 flex flex-wrap items-end gap-3">
      <div>
        <label class="mb-1 block text-xs font-medium text-slate-500 dark:text-slate-400">Fecha del sorteo</label>
        <AppDatePicker v-model="searchDate" :allowed-dates="allowedDates" />
      </div>
      <button
        type="button"
        class="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-700"
        @click="applySearch"
      >
        Buscar
      </button>
      <button
        type="button"
        class="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
        @click="clearSearch"
      >
        Limpiar
      </button>
    </div>

    <div class="overflow-hidden rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <div class="overflow-x-auto">
        <table class="w-full text-left text-sm">
          <thead class="border-b border-slate-200 bg-slate-50 text-slate-500 dark:border-slate-800 dark:bg-slate-800/50 dark:text-slate-400">
            <tr>
              <th scope="col" class="px-4 py-3 font-medium">Sorteo</th>
              <th scope="col" class="px-4 py-3 font-medium">Fecha</th>
              <th scope="col" class="px-4 py-3 font-medium">Números</th>
              <th scope="col" class="px-4 py-3 text-right font-medium">Acumulado</th>
              <th scope="col" class="px-4 py-3 font-medium">Cayó</th>
              <th scope="col" class="px-4 py-3"><span class="sr-only">Detalles</span></th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 dark:divide-slate-800">
            <tr v-if="loading">
              <td colspan="6" class="px-4 py-10 text-center text-slate-400 dark:text-slate-500">Cargando…</td>
            </tr>
            <tr v-else-if="error">
              <td colspan="6" class="px-4 py-10 text-center text-red-500">{{ error }}</td>
            </tr>
            <tr v-else-if="!result || result.items.length === 0">
              <td colspan="6" class="px-4 py-10 text-center text-slate-400 dark:text-slate-500">
                No hay sorteos para mostrar.
              </td>
            </tr>
            <template v-else>
              <tr
                v-for="draw in result.items"
                :key="draw.game_id"
                class="hover:bg-slate-50 dark:hover:bg-slate-800/40"
              >
                <td class="px-4 py-3 font-medium tabular-nums text-slate-900 dark:text-white">
                  {{ draw.game_id }}
                </td>
                <td class="px-4 py-3 whitespace-nowrap text-slate-600 dark:text-slate-300">
                  {{ draw.game_date }}
                </td>
                <td class="px-4 py-3">
                  <div class="flex flex-wrap gap-1.5">
                    <NumberBall v-for="n in draw.numbers" :key="n" :value="n" />
                  </div>
                </td>
                <td class="px-4 py-3 text-right tabular-nums text-slate-900 dark:text-white">
                  {{ draw.accumulated }}
                </td>
                <td class="px-4 py-3">
                  <span
                    v-if="draw.jackpot"
                    class="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400"
                  >
                    Sí
                  </span>
                  <span
                    v-else
                    class="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400"
                  >
                    No
                  </span>
                </td>
                <td class="px-4 py-3 text-right">
                  <RouterLink
                    :to="`/miloto/draw/${draw.game_id}`"
                    class="font-medium text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300"
                  >
                    Detalles
                  </RouterLink>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <AppPagination
        v-if="result"
        :page="result.page"
        :pages="result.pages"
        :total="result.total"
        :size="result.size"
        @first="goToPage(1)"
        @previous="goToPage(pageFromQuery - 1)"
        @next="goToPage(pageFromQuery + 1)"
        @last="goToPage(result.pages)"
      />
    </div>
  </div>
</template>
