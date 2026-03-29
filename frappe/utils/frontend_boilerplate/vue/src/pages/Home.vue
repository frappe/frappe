<template>
  <div class="mx-auto max-w-3xl px-6 py-8">
    <div class="mb-6 flex items-center justify-between">
      <h1 class="text-2xl font-semibold text-ink-gray-9">ToDos</h1>
      <Button variant="solid" @click="showNewDialog = true">
        <template #prefix>
          <LucidePlus class="h-4 w-4" />
        </template>
        New ToDo
      </Button>
    </div>

    <div v-if="todos.data?.length" class="space-y-2">
      <router-link
        v-for="todo in todos.data"
        :key="todo.name"
        :to="{ name: 'TodoDetail', params: { id: todo.name } }"
        class="flex items-center justify-between rounded-lg border bg-surface-white px-4 py-3 transition hover:bg-surface-gray-1"
      >
        <div class="flex items-center gap-3">
          <button
            class="flex h-5 w-5 items-center justify-center rounded border transition"
            :class="[
              todo.status === 'Closed'
                ? 'border-green-600 bg-green-600'
                : 'border-outline-gray-3 hover:border-outline-gray-5',
            ]"
            @click.prevent="toggleStatus(todo)"
          >
            <LucideCheck v-if="todo.status === 'Closed'" class="h-3.5 w-3.5 text-white" />
          </button>
          <span
            class="text-sm"
            :class="[
              todo.status === 'Closed'
                ? 'text-ink-gray-5 line-through'
                : 'text-ink-gray-9',
            ]"
          >
            {% raw %}{{ todo.description || 'Untitled' }}{% endraw %}
          </span>
        </div>
        <div class="flex items-center gap-2">
          <Badge
            v-if="todo.priority"
            :variant="'subtle'"
            :theme="priorityColor(todo.priority)"
            size="sm"
          >
            {% raw %}{{ todo.priority }}{% endraw %}
          </Badge>
          <button
            class="rounded p-1 text-ink-gray-5 transition hover:bg-surface-gray-2 hover:text-ink-red-7"
            @click.prevent="deleteTodo(todo.name)"
          >
            <LucideTrash2 class="h-3.5 w-3.5" />
          </button>
        </div>
      </router-link>
    </div>

    <div
      v-else-if="!todos.loading"
      class="flex flex-col items-center justify-center rounded-lg border border-dashed py-12 text-ink-gray-5"
    >
      <LucideListTodo class="mb-3 h-10 w-10 text-ink-gray-4" />
      <p class="text-sm">No ToDos yet. Create one to get started.</p>
    </div>

    <Dialog v-model="showNewDialog" :options="{ title: 'New ToDo' }">
      <template #body-content>
        <div class="space-y-4">
          <FormControl
            label="Description"
            v-model="newTodo.description"
            type="textarea"
            placeholder="What needs to be done?"
          />
          <FormControl
            label="Priority"
            v-model="newTodo.priority"
            type="select"
            :options="['Low', 'Medium', 'High']"
          />
        </div>
      </template>
      <template #actions>
        <Button
          variant="solid"
          class="w-full"
          @click="createTodo"
          :loading="creating"
        >
          Create
        </Button>
      </template>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useTodoList } from '@/data/todos'

const todos = useTodoList()
const showNewDialog = ref(false)
const creating = ref(false)

const newTodo = reactive({
  description: '',
  priority: 'Medium',
})

function priorityColor(priority: string) {
  switch (priority) {
    case 'High':
      return 'red'
    case 'Medium':
      return 'orange'
    case 'Low':
      return 'blue'
    default:
      return 'gray'
  }
}

async function createTodo() {
  creating.value = true
  try {
    await todos.insert.submit({
      description: newTodo.description,
      priority: newTodo.priority,
      status: 'Open',
    })
    showNewDialog.value = false
    newTodo.description = ''
    newTodo.priority = 'Medium'
    todos.reload()
  } finally {
    creating.value = false
  }
}

async function toggleStatus(todo: any) {
  const newStatus = todo.status === 'Closed' ? 'Open' : 'Closed'
  todo.status = newStatus
  await todos.setValue.submit({ name: todo.name, status: newStatus })
  todos.reload()
}

async function deleteTodo(name: string) {
  await todos.delete.submit({ name })
  todos.reload()
}
</script>
