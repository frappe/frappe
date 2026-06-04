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

const doc = reactive<Record<string, any>>({ reference_id: 'REF-0001' })

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
        name: 'conditional',
        label: 'Conditional',
        columns: [
          {
            name: 'cond-col',
            fields: [
              { fieldname: 'has_owner', fieldtype: 'Check', label: 'Assign an owner' },
              {
                fieldname: 'assigned_to',
                fieldtype: 'Link',
                label: 'Assigned To',
                options: 'User',
                // Shown only when the controlling check is ticked, and required then.
                dependsOn: 'eval:doc.has_owner',
                mandatoryDependsOn: 'eval:doc.has_owner',
              },
              {
                fieldname: 'reference_id',
                fieldtype: 'Data',
                label: 'Reference ID (read-only)',
                readOnly: true,
              },
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
