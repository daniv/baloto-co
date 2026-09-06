<script setup lang="ts">
withDefaults(defineProps<{ value: number; size?: 'sm' | 'lg'; accent?: boolean }>(), {
  size: 'sm',
  accent: false,
})
</script>

<template>
  <span
    class="flex items-center justify-center rounded-full border font-semibold tabular-nums"
    :class="[
      size === 'lg' ? 'h-14 w-14 text-xl' : 'h-8 w-8 text-xs',
      accent
        ? 'border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-400'
        : 'border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200',
    ]"
  >
    {{ value }}
  </span>
</template>
