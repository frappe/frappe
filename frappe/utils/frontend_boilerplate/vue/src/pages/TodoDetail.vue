<template>
  <div class="mx-auto max-w-3xl px-6 py-8">
    <div class="mb-6">
      <router-link
        :to="{ name: 'Home' }"
        class="inline-flex items-center gap-1 text-sm text-ink-gray-5 transition hover:text-ink-gray-8"
      >
        <LucideArrowLeft class="h-4 w-4" />
        Back to ToDos
      </router-link>
    </div>

    <div v-if="todo.doc" class="space-y-6">
      <div class="flex items-start justify-between">
        <h1 class="text-2xl font-semibold text-ink-gray-9">
          {% raw %}{{ todo.doc.description || 'Untitled ToDo' }}{% endraw %}
        </h1>
        <div class="flex items-center gap-2">
          <Badge
            :variant="'subtle'"
            :theme="todo.doc.status === 'Closed' ? 'green' : 'orange'"
            size="md"
          >
            {% raw %}{{ todo.doc.status }}{% endraw %}
          </Badge>
          <Button variant="ghost" theme="red" @click="onDelete">
            <LucideTrash2 class="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div class="rounded-lg border bg-surface-white p-6">
        <div class="space-y-4">
          <FormControl
            label="Description"
            type="textarea"
            :modelValue="todo.doc.description"
            @update:modelValue="(val: string) => todo.setValue.submit({ description: val })"
          />
          <div class="grid grid-cols-2 gap-4">
            <FormControl
              label="Status"
              type="select"
              :options="['Open', 'Closed', 'Cancelled']"
              :modelValue="todo.doc.status"
              @update:modelValue="(val: string) => todo.setValue.submit({ status: val })"
            />
            <FormControl
              label="Priority"
              type="select"
              :options="['Low', 'Medium', 'High']"
              :modelValue="todo.doc.priority"
              @update:modelValue="(val: string) => todo.setValue.submit({ priority: val })"
            />
          </div>
          <FormControl
            label="Due Date"
            type="date"
            :modelValue="todo.doc.date"
            @update:modelValue="(val: string) => todo.setValue.submit({ date: val })"
          />
        </div>
      </div>

      <div class="text-xs text-ink-gray-5">
        Last modified: {% raw %}{{ todo.doc.modified }}{% endraw %}
      </div>
    </div>

    <div v-else-if="todo.loading" class="flex items-center justify-center py-12">
      <div class="text-sm text-ink-gray-5">Loading...</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useTodo } from '@/data/todos'

const props = defineProps<{
  id: string
}>()

const router = useRouter()
const todo = useTodo(props.id)

async function onDelete() {
  await todo.delete.submit()
  router.push({ name: 'Home' })
}
</script>
