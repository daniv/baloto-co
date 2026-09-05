<script setup lang="ts">
const props = defineProps<{
  page: number
  pages: number
  total: number
  size: number
}>()

const emit = defineEmits<{ first: []; previous: []; next: []; last: [] }>()

function rangeLabel(): string {
  if (props.total === 0) return 'Sin resultados'
  const from = (props.page - 1) * props.size + 1
  const to = Math.min(props.page * props.size, props.total)
  return `Mostrando ${from}–${to} de ${props.total} resultados`
}
</script>

<template>
  <div
    class="flex flex-col items-center justify-between gap-3 border-t border-slate-200 px-4 py-3 sm:flex-row dark:border-slate-800"
  >
    <p class="text-sm text-slate-500 dark:text-slate-400">{{ rangeLabel() }}</p>

    <div class="flex items-center gap-2">
      <button
        v-if="page > 1"
        type="button"
        class="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
        @click="emit('first')"
      >
        &lt;&lt; Inicio
      </button>
      <button
        v-if="page > 1"
        type="button"
        class="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
        @click="emit('previous')"
      >
        Anterior
      </button>

      <span class="px-1 text-sm text-slate-500 dark:text-slate-400">
        Página {{ pages === 0 ? 0 : page }} de {{ pages }}
      </span>

      <button
        v-if="page < pages"
        type="button"
        class="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
        @click="emit('next')"
      >
        Siguiente
      </button>
      <button
        v-if="page < pages"
        type="button"
        class="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
        @click="emit('last')"
      >
        Última &gt;&gt;
      </button>
    </div>
  </div>
</template>
