import { useList, useDoc } from 'frappe-ui'
import type { ToDo } from '@/types'

export function useTodoList() {
  return useList<ToDo>({
    doctype: 'ToDo',
    fields: ['name', 'description', 'status', 'priority', 'date', 'modified'],
    orderBy: 'modified desc',
    limit: 20,
    immediate: true,
  })
}

const todoCache: Record<string, ReturnType<typeof useDoc>> = {}

export function useTodo(name: string) {
  if (!todoCache[name]) {
    todoCache[name] = useDoc<ToDo>({
      doctype: 'ToDo',
      name,
    })
  }
  return todoCache[name] as ReturnType<typeof useDoc<ToDo>>
}
