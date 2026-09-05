<script setup lang="ts">
const props = defineProps<{
  page: number
  pages: number
  total: number
  size: number
  pageSizeOptions?: number[]
}>()

const emit = defineEmits<{ first: []; previous: []; next: []; last: []; 'update:size': [number] }>()

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
    <div class="flex items-center gap-3">
      <p class="text-sm text-slate-500 dark:text-slate-400">{{ rangeLabel() }}</p>
      <label v-if="pageSizeOptions" class="flex items-center gap-1.5 text-sm text-slate-500 dark:text-slate-400">
        Mostrar
        <select
          :value="size"
          class="rounded-md border border-slate-300 bg-white px-1.5 py-1 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
          @change="emit('update:size', Number(($event.target as HTMLSelectElement).value))"
        >
          <option v-for="opt in pageSizeOptions" :key="opt" :value="opt">{{ opt }}</option>
        </select>
      </label>
    </div>

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
