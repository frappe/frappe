declare module 'virtual:frappe/contributions' {
  import type { Contributions } from '@/contributions/types'
  const contributions: Contributions
  export default contributions
}

declare module 'virtual:frappe/list-scripts' {
  import type { ListScriptContribution } from '@/contributions/types'
  const listScripts: ListScriptContribution[]
  export default listScripts
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}
