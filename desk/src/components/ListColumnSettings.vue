<template>
    <NestedPopover>
        <template #target>
            <Button :label="'Columns'">
                <template #prefix>
                    <FeatherIcon name="columns" class="h-4" />
                </template>
            </Button>
        </template>
        <template #body="{ close }">
            <div class="my-2 rounded-lg border border-gray-100 bg-white p-1.5 shadow-xl w-[15rem]">
                <div>
                    <Draggable :list="columns" item-key="key" class="list-group">
                        <template #item="{ element }">
                            <div
                                class="flex cursor-grab items-center justify-between gap-6 rounded px-2 py-1.5 text-base text-gray-800 hover:bg-gray-100">
                                <div class="flex items-center gap-2">
                                    <Icon :name="'es-line-drag'" class="h-2.5 w-2.5 text-gray-600"/>
                                    <div>{{ element.label }}</div>
                                </div>
                                <div class="flex cursor-pointer items-center gap-1">
                                    <Button variant="ghost" class="!h-5 w-5 !p-1" @click="removeColumn(element)">
                                        <FeatherIcon name="x" class="h-3.5 w-3.5" />
                                    </Button>
                                </div>
                            </div>
                        </template>
                    </Draggable>
                    <div class="mt-1.5 flex flex-col gap-1 border-t pt-1.5">
                        <Autocomplete :body-classes="'w-[14rem]'" :options="fields" @update:modelValue="(e) => addColumn(e)">
                            <template #target="{ togglePopover }">
                                <Button class="w-full !justify-start !text-gray-600" variant="ghost"
                                    @click="togglePopover()" :label="'Add Column'">
                                    <template #prefix>
                                        <FeatherIcon name="plus" class="h-4" />
                                    </template>
                                </Button>
                            </template>
                        </Autocomplete>
                        <Button v-if="columnsUpdated" class="w-full !justify-start !text-gray-600" variant="ghost"
                            @click="reset(close)" :label="'Reset Changes'">
                            <template #prefix>
                                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" class="h-4"><path d="M2.35619 8.42909C2.35644 9.77009 2.84031 11.066 3.719 12.079C4.5977 13.092 5.81226 13.7542 7.13977 13.9439C8.46729 14.1336 9.8187 13.8382 10.946 13.1119C12.0732 12.3856 12.9008 11.2771 13.2766 9.98982C13.6525 8.70258 13.5515 7.32295 12.9922 6.10414C12.4329 4.88534 11.4528 3.90914 10.2318 3.35469C9.0108 2.80025 7.63079 2.70476 6.34504 3.08576C5.0593 3.46675 3.95409 4.29867 3.23226 5.42883" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"></path><path d="M3.21297 2V5.42886H6.64183" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"></path></svg>
                            </template>
                        </Button>
                    </div>
                </div>
            </div>
        </template>
    </NestedPopover>
</template>

<script setup>
import NestedPopover from '@/components/NestedPopover.vue';
import { Autocomplete, FeatherIcon } from 'frappe-ui';
import Draggable from 'vuedraggable';
import { computed, ref, watch } from 'vue';

const props = defineProps({
    allColumns: {
        type: Array,
        default: [],
    },
})

const columns = defineModel();

const oldValues = ref({});

function addColumn(c) {
    let _column = {
        label: c.label,
        type: c.type,
        key: c.value,
        width: '10rem',
    }
    columns.value.push(_column);
}

const fields = computed(() => {
    let allFields = props.allColumns;
    if (!allFields) return [];

    return allFields.filter((field) => {
        return !columns.value.find((column) => column.key === field.value);
    })
});


function removeColumn(c) {
    columns.value = columns.value.filter((column) => column.key !== c.key);
}

function reset(close) {
    columns.value = Array.from(oldValues.value.columns);
    close();
}

watch(
    columns.value,
    (columns) => {
        if (!columns) return;
        oldValues.value.columns = JSON.parse(JSON.stringify(columns));
    },
    { once: true, immediate: true }
);

const columnsUpdated = computed(() => JSON.stringify(oldValues.value.columns) != JSON.stringify(columns.value));

</script>