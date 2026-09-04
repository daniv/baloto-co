<script setup lang="ts">
defineProps<{ value: number }>()
</script>

<template>
  <span
    class="flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-slate-50 text-xs font-semibold tabular-nums text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
  >
    {{ value }}
  </span>
</template>
