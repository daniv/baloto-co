<script setup lang="ts">
import AppIcon from '@/components/ui/AppIcon.vue'
import { navItems } from './navItems'
</script>

<template>
  <aside
    class="hidden w-64 shrink-0 flex-col border-r border-slate-200 bg-white lg:flex dark:border-slate-800 dark:bg-slate-900"
  >
    <div class="flex h-16 items-center gap-2 px-6">
      <div
        class="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white"
      >
        B
      </div>
      <span class="text-base font-semibold tracking-tight text-slate-900 dark:text-white">
        Baloto&nbsp;Co
      </span>
    </div>

    <nav class="flex-1 space-y-1 px-3 py-4">
      <p class="px-3 pb-2 text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
        Resultados
      </p>
      <RouterLink
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        class="group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-white"
        active-class="!bg-brand-50 !text-brand-700 dark:!bg-brand-500/10 dark:!text-brand-400"
      >
        <AppIcon :name="item.icon" class="h-5 w-5 shrink-0" />
        {{ item.label }}
      </RouterLink>
    </nav>

    <div class="border-t border-slate-200 px-6 py-4 text-xs text-slate-400 dark:border-slate-800 dark:text-slate-500">
      &copy; {{ new Date().getFullYear() }} Baloto Co
    </div>
  </aside>
</template>
