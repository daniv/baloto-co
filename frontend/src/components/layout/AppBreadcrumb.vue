<script setup lang="ts">
import AppIcon from '@/components/ui/AppIcon.vue'
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const crumbs = computed(() => {
  if (route.name === 'home') return []
  const trail = route.meta.parent ? [route.meta.parent] : []
  return [...trail, { label: route.meta.breadcrumb, to: route.path }]
})
</script>

<template>
  <nav aria-label="Breadcrumb" class="flex items-center gap-1.5 text-sm">
    <RouterLink
      to="/"
      class="flex items-center gap-1.5 text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
    >
      <AppIcon name="home" class="h-4 w-4" />
      <span>Inicio</span>
    </RouterLink>
    <template v-for="(crumb, index) in crumbs" :key="crumb.to">
      <AppIcon name="chevron-right" class="h-3.5 w-3.5 text-slate-300 dark:text-slate-600" />
      <RouterLink
        v-if="index < crumbs.length - 1"
        :to="crumb.to"
        class="text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
      >
        {{ crumb.label }}
      </RouterLink>
      <span v-else class="font-medium text-slate-900 dark:text-white">{{ crumb.label }}</span>
    </template>
  </nav>
</template>
