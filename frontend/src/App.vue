<script setup lang="ts">
import AppSidebar from '@/components/layout/AppSidebar.vue'
import AppTopbar from '@/components/layout/AppTopbar.vue'
import { navItems } from '@/components/layout/navItems'
import AppIcon from '@/components/ui/AppIcon.vue'
import { useThemeStore } from '@/stores/theme'
import { ref } from 'vue'

const themeStore = useThemeStore()
themeStore.init()

const mobileNavOpen = ref(false)
</script>

<template>
  <div class="flex min-h-screen bg-slate-50 dark:bg-slate-950">
    <AppSidebar />

    <!-- Mobile nav drawer -->
    <div v-if="mobileNavOpen" class="fixed inset-0 z-20 lg:hidden">
      <div class="absolute inset-0 bg-slate-900/40" @click="mobileNavOpen = false" />
      <aside class="relative flex h-full w-64 flex-col bg-white dark:bg-slate-900">
        <div class="flex h-16 items-center gap-2 px-6">
          <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">
            B
          </div>
          <span class="text-base font-semibold tracking-tight text-slate-900 dark:text-white">Baloto&nbsp;Co</span>
        </div>
        <nav class="flex-1 space-y-1 px-3 py-4">
          <RouterLink
            v-for="item in navItems"
            :key="item.to"
            :to="item.to"
            class="group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-white"
            active-class="!bg-brand-50 !text-brand-700 dark:!bg-brand-500/10 dark:!text-brand-400"
            @click="mobileNavOpen = false"
          >
            <AppIcon :name="item.icon" class="h-5 w-5 shrink-0" />
            {{ item.label }}
          </RouterLink>
        </nav>
      </aside>
    </div>

    <div class="flex min-w-0 flex-1 flex-col">
      <AppTopbar @toggle-sidebar="mobileNavOpen = true" />
      <main class="flex-1 px-4 py-6 sm:px-6 lg:px-8">
        <RouterView />
      </main>
    </div>
  </div>
</template>
