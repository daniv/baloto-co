import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    breadcrumb: string
    parent?: { label: string; to: string }
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
    meta: { breadcrumb: 'Inicio' },
  },
  {
    path: '/miloto',
    name: 'miloto',
    component: () => import('@/views/MilotoView.vue'),
    meta: { breadcrumb: 'Miloto' },
  },
  {
    path: '/miloto/draw/:id',
    name: 'miloto-draw-detail',
    component: () => import('@/views/MilotoDrawDetailView.vue'),
    meta: { breadcrumb: 'Detalle del sorteo', parent: { label: 'Miloto', to: '/miloto' } },
  },
  {
    path: '/baloto-revancha',
    name: 'baloto-revancha',
    component: () => import('@/views/BalotoRevanchaView.vue'),
    meta: { breadcrumb: 'Baloto / Revancha' },
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})
