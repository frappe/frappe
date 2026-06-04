<template>
  <div class="p-6 max-w-3xl">
    <FormLayout v-model:doc="doc" :layout="layout" @change="onChange" />
    <pre class="mt-6 text-xs text-ink-gray-6">doc = {{ doc }}</pre>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import FormLayout from '../FormLayout.vue'
import type { FormLayoutSchema } from '../types'

const doc = reactive<Record<string, any>>({})

const layout: FormLayoutSchema = [
  {
    name: 'details',
    label: 'Details',
    sections: [
      {
        name: 'people',
        label: 'People',
        columns: [
          {
            name: 'col1',
            fields: [
              { fieldname: 'owner', fieldtype: 'Link', label: 'Owner', options: 'User' },
            ],
          },
          {
            name: 'col2',
            fields: [
              { fieldname: 'title', fieldtype: 'Data', label: 'Title', placeholder: 'Enter a title' },
            ],
          },
        ],
      },
      {
        name: 'fieldtypes',
        label: 'Fieldtypes',
        columns: [
          {
            name: 'col-a',
            fields: [
              { fieldname: 'status', fieldtype: 'Select', label: 'Status', options: 'Open\nIn Progress\nClosed' },
              { fieldname: 'active', fieldtype: 'Check', label: 'Active' },
              { fieldname: 'due_date', fieldtype: 'Date', label: 'Due Date' },
              { fieldname: 'remind_at', fieldtype: 'Datetime', label: 'Remind At' },
              { fieldname: 'start_time', fieldtype: 'Time', label: 'Start Time' },
            ],
          },
          {
            name: 'col-b',
            fields: [
              { fieldname: 'quantity', fieldtype: 'Int', label: 'Quantity' },
              { fieldname: 'amount', fieldtype: 'Currency', label: 'Amount' },
              { fieldname: 'progress', fieldtype: 'Percent', label: 'Progress' },
              { fieldname: 'notes', fieldtype: 'Text', label: 'Notes', placeholder: 'Add notes' },
              { fieldname: 'secret', fieldtype: 'Password', label: 'Secret' },
            ],
          },
        ],
      },
      {
        name: 'misc',
        label: 'Miscellaneous',
        collapsible: true,
        opened: false,
        columns: [
          {
            name: 'col3',
            fields: [
              { fieldname: 'mystery', fieldtype: 'SomethingUnknown', label: 'Unknown fieldtype (falls back to text)' },
            ],
          },
        ],
      },
    ],
  },
]

function onChange(fieldname: string, value: any) {
  console.log('change', fieldname, value)
}
</script>
