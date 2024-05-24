<template>
    <NestedPopover>
        <template #target>
            <Button :label="'Filter'">
                <template #prefix>
                    <FeatherIcon name="filter" class="h-3.5" />
                </template>
                <template v-if="filters.length" #suffix>
                    <div
                        class="flex h-5 w-5 items-center justify-center rounded bg-gray-900 pt-[1px] text-2xs font-medium text-white">
                        {{ filters.length }}
                    </div>
                </template>
            </Button>
        </template>
        <template #body="{ close }">
            <div class="my-2 rounded-lg border border-gray-100 bg-white shadow-xl">
                <div class="w-[32rem] p-2">
                    <div v-if="filters.length" v-for="(filter, i) in filters" id="filter-list"
                        class="mb-3 flex items-center justify-between gap-2">
                        <div class="flex items-center gap-2">
                            <div class="w-13 pl-2 text-end text-base text-gray-600">
                                {{ i == 0 ? 'Where' : 'And' }}
                            </div>
                            <div id="fieldname" class="w-[9rem]">
                                <Autocomplete :body-classes="'w-[15rem]'" :modelValue="filter.field"
                                    :options="allFilterableFields"
                                    @update:model-value="(option) => filter.field = option.value" />
                            </div>
                            <div id="operator" class="w-[6rem]">
                                <FormControl type="select" v-model="filter.operator"
                                    :options="getOperators(filter.field)" @change="filter.value = ''" />
                            </div>
                            <div id="value" class="w-[9rem]">
                                <component :is="getValSelect(filter)" v-model="filter.value"
                                    @change="updateValue(filter)" />
                            </div>
                        </div>
                        <Button variant="ghost" icon="x" @click="filters.splice(i, 1)" />
                    </div>
                    <div v-else class="mb-3 flex h-7 items-center px-3 text-sm text-gray-600">
                        {{ 'Empty - Choose a field to filter by' }}
                    </div>
                    <div class="flex items-center justify-between gap-2">
                        <Autocomplete :body-classes="'w-[29rem]'" :options="allFilterableFields"
                            @update:model-value="(option) => addFilter(option)">
                            <template #target="{ togglePopover }">
                                <Button class="!text-gray-600" variant="ghost" @click="togglePopover()"
                                    :label="'Add Filter'">
                                    <template #prefix>
                                        <FeatherIcon name="plus" class="h-4" />
                                    </template>
                                </Button>
                            </template>
                        </Autocomplete>
                        <Button v-if="filters.length" class="!text-gray-600" variant="ghost" :label="'Clear'"
                            @click="clearFilters(close)" />
                    </div>
                </div>
            </div>
        </template>
    </NestedPopover>
</template>

<script setup>
import DatePicker from '@/components/Controls/DatePicker.vue'
import DatetimePicker from '@/components/Controls/DatetimePicker.vue'
import DateRangePicker from '@/components/Controls/DateRangePicker.vue'
import Link from '@/components/Controls/Link.vue'

import NestedPopover from './NestedPopover.vue';
import { Button, FeatherIcon, Autocomplete, FormControl } from 'frappe-ui';
import { h } from 'vue';

const props = defineProps({
    allFilterableFields: {
        type: Array,
        default: [],
    },
});

const emit = defineEmits(['update']);

const filters = defineModel();

const getFieldType = (fieldname) => {
    return props.allFilterableFields.find((f) => f.value === fieldname).type || '';
};

function getOperators(fieldname) {
    let fieldtype = getFieldType(fieldname);
    let options = []
    if (typeString.includes(fieldtype)) {
        options.push(
            ...[
                { label: 'Equals', value: '=' },
                { label: 'Not Equals', value: '!=' },
                { label: 'Like', value: 'like' },
                { label: 'Not Like', value: 'not like' },
                { label: 'In', value: 'in' },
                { label: 'Not In', value: 'not in' },
                { label: 'Is', value: 'is' },
            ]
        )
    }
    if (fieldname === '_assign') {
        // TODO: make equals and not equals work
        options = [
            { label: 'Like', value: 'like' },
            { label: 'Not Like', value: 'not like' },
            { label: 'Is', value: 'is' },
        ]
    }
    if (typeNumber.includes(fieldtype)) {
        options.push(
            ...[
                { label: 'Equals', value: '=' },
                { label: 'Not Equals', value: '!=' },
                { label: 'Like', value: 'like' },
                { label: 'Not Like', value: 'not like' },
                { label: 'In', value: 'in' },
                { label: 'Not In', value: 'not in' },
                { label: 'Is', value: 'is' },
                { label: '<', value: '<' },
                { label: '>', value: '>' },
                { label: '<=', value: '<=' },
                { label: '>=', value: '>=' },
            ]
        )
    }
    if (typeSelect.includes(fieldtype)) {
        options.push(
            ...[
                { label: 'Equals', value: '=' },
                { label: 'Not Equals', value: '!=' },
                { label: 'In', value: 'in' },
                { label: 'Not In', value: 'not in' },
                { label: 'Is', value: 'is' },
            ]
        )
    }
    if (typeLink.includes(fieldtype)) {
        options.push(
            ...[
                { label: 'Equals', value: '=' },
                { label: 'Not Equals', value: '!=' },
                { label: 'Like', value: 'like' },
                { label: 'Not Like', value: 'not like' },
                { label: 'In', value: 'in' },
                { label: 'Not In', value: 'not in' },
                { label: 'Is', value: 'is' },
            ]
        )
    }
    if (typeCheck.includes(fieldtype)) {
        options.push(...[{ label: 'Equals', value: '=' }])
    }
    if (['Duration'].includes(fieldtype)) {
        options.push(
            ...[
                { label: 'Like', value: 'like' },
                { label: 'Not Like', value: 'not like' },
                { label: 'In', value: 'in' },
                { label: 'Not In', value: 'not in' },
                { label: 'Is', value: 'is' },
            ]
        )
    }
    if (typeDate.includes(fieldtype)) {
        options.push(
            ...[
                { label: 'Is', value: 'is' },
                { label: '>', value: '>' },
                { label: '<', value: '<' },
                { label: '>=', value: '>=' },
                { label: '<=', value: '<=' },
                { label: 'Between', value: 'between' },
                { label: 'Timespan', value: 'timespan' },
            ]
        )
    }
    return options
}

const typeCheck = ['Check']
const typeLink = ['Link', 'Dynamic Link']
const typeNumber = ['Float', 'Int', 'Currency', 'Percent']
const typeSelect = ['Select']
const typeString = ['Data', 'Long Text', 'Small Text', 'Text Editor', 'Text']
const typeDate = ['Date', 'Datetime']
const timespanOptionsList = [
    {
        label: 'Last Week',
        value: 'last week',
    },
    {
        label: 'Last Month',
        value: 'last month',
    },
    {
        label: 'Last Quarter',
        value: 'last quarter',
    },
    {
        label: 'Last 6 Months',
        value: 'last 6 months',
    },
    {
        label: 'Last Year',
        value: 'last year',
    },
    {
        label: 'Yesterday',
        value: 'yesterday',
    },
    {
        label: 'Today',
        value: 'today',
    },
    {
        label: 'Tomorrow',
        value: 'tomorrow',
    },
    {
        label: 'This Week',
        value: 'this week',
    },
    {
        label: 'This Month',
        value: 'this month',
    },
    {
        label: 'This Quarter',
        value: 'this quarter',
    },
    {
        label: 'This Year',
        value: 'this year',
    },
    {
        label: 'Next Week',
        value: 'next week',
    },
    {
        label: 'Next Month',
        value: 'next month',
    },
    {
        label: 'Next Quarter',
        value: 'next quarter',
    },
    {
        label: 'Next 6 Months',
        value: 'next 6 months',
    },
    {
        label: 'Next Year',
        value: 'next year',
    },
]

function getValSelect(f) {
    const { field, operator } = f;
    const fieldtype = getFieldType(field);
    const options = props.allFilterableFields.find((f) => f.value === field).options;
    if (operator == 'is') {
        return h(FormControl, {
            type: 'select',
            options: [
                {
                    label: 'Set',
                    value: 'set',
                },
                {
                    label: 'Not Set',
                    value: 'not set',
                },
            ],
        })
    } else if (operator == 'timespan') {
        return h(FormControl, {
            type: 'select',
            options: timespanOptionsList,
        })
    } else if (['like', 'not like', 'in', 'not in'].includes(operator)) {
        return h(FormControl, { type: 'text' })
    } else if (typeSelect.includes(fieldtype) || typeCheck.includes(fieldtype)) {
        const _options =
            fieldtype == 'Check' ? ['Yes', 'No'] : getSelectOptions(options)
        let check_values = { 'Yes': true, 'No': false };
        return h(FormControl, {
            type: 'select',
            options: _options.map((o) => ({
                label: o,
                value: check_values[o] || o,
            })),
        })
    } else if (typeLink.includes(fieldtype)) {
        if (fieldtype == 'Dynamic Link') {
            return h(FormControl, { type: 'text' })
        }
        return h(Link, { class: 'form-control', doctype: options, value: f.value })
    } else if (typeNumber.includes(fieldtype)) {
        return h(FormControl, { type: 'number' })
    } else if (typeDate.includes(fieldtype) && operator == 'between') {
        return h(DateRangePicker, { value: f.value })
    } else if (typeDate.includes(fieldtype)) {
        return h(fieldtype == 'Date' ? DatePicker : DatetimePicker, {
            value: f.value,
        })
    } else {
        return h(FormControl, { type: 'text' })
    }
}

function updateValue(filter){
    emit('update', filter);
}
</script>