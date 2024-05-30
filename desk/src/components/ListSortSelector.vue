<template>
    <div v-if="sort" class="rounded w-[12rem] flex">
        <div class="w-[2rem]">
            <Button class="w-full rounded-none rounded-l border bg-gray-100" @click="toggleSortOrder">
                <template #icon>
                    <Icon :name="sort[1] == 'ASC' ? 'sort-ascending' : 'sort-descending'" class="h-3.5 w-3.5">
                    </Icon>
                </template>
            </Button>
        </div>
        <Dropdown :options="sortOptions">
            <template v-slot="{ open }">
                <Button variant="ghost"
                    class="border w-[10rem] flex items-center justify-between gap-1 rounded-l-none border border-l-0 hover:bg-inherit">
                    <span>{{ sortField }}</span>
                    <template #suffix>
                        <FeatherIcon :name="open ? 'chevron-up' : 'chevron-down'" class="h-4 w-4" />
                    </template>
                </Button>
            </template>
        </Dropdown>
    </div>
</template>

<script setup>
import { ref, computed, defineModel } from 'vue';
import { Button } from 'frappe-ui';
import { Dropdown, FeatherIcon } from 'frappe-ui';

const sort = defineModel();

const props = defineProps({
    allSortableFields: {
        type: Array,
        default: []
    }
});

const toggleSortOrder = () => {
    sort.value[1] = sort.value[1] == 'ASC' ? 'DESC' : 'ASC';
};

const sortField = computed(() => {
    const field = props.allSortableFields.find(field => field.key === sort.value[0]);
    return field ? field.label : '';
});

const sortOptions = computed(() => {
    return props.allSortableFields.map(field => {
        return {
            label: field.label,
            onClick: () => {
                sort.value[0] = field.key;
            }
        };
    });
});

</script>