declare module 'virtual:frappe/contributions' {
  import type { Contributions } from '@/contributions/types'
  const contributions: Contributions
  export default contributions
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}
