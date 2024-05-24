<template>
  <div v-if="list_config.columns" class="m-6 mt-4 flex flex-col gap-4">
    <template v-if="options.showColumnSettings">
      <ListControls v-model="list_config" :options="options"
        @updateConfigSettings="emit('update', { 'columns': list_config.columns })"
        @filterChange="(f) => emit('filterChange', f)">
        <template #customControls>
          <slot name="customControls"></slot>
        </template>
      </ListControls>
    </template>
    <List :rows="list_config.rows" :rowKey="list_config.rowKey" :columns="list_config.columns" :options="options" />
  </div>
</template>

<script setup>
import { defineProps, defineEmits, defineModel, computed } from 'vue';
import { ListView as List } from 'frappe-ui';
import ListControls from '@/components/ListControls.vue';

const emit = defineEmits(['update', 'filterChange']);

const list_config = defineModel();

const props = defineProps({
  options: {
    type: Object,
    default: () => ({
      getRowRoute: null,
      onRowClick: null,
      showTooltip: true,
      selectable: true,
      resizeColumn: false,
      rowHeight: 40,
      showColumnSettings: true,
      showFilters: true,
    }),
  },
});
</script>