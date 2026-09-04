<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()
</script>

<template>
  <div>
    <h1 class="text-2xl font-semibold tracking-tight text-slate-900 dark:text-white">
      Sorteo Miloto #{{ route.params.id }}
    </h1>
    <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">Detalle del sorteo próximamente.</p>
  </div>
</template>
