<template>
  <Popover
    @open="selectCurrentMonthYear"
    class="flex w-full [&>div:first-child]:w-full"
  >
    <template #target="{ togglePopover }">
      <input
        readonly
        type="text"
        :placeholder="placeholder"
        :value="value && formatter ? formatter(value) : value"
        @focus="!readonly ? togglePopover() : null"
        :class="[
          'form-input  block h-7 w-full cursor-pointer select-none rounded border-gray-400 text-sm placeholder-gray-500',
          inputClass,
        ]"
        v-bind="$attrs"
      />
    </template>
    <template #body="{ togglePopover }">
      <div
        class="mt-2 w-fit select-none divide-y rounded-lg bg-white text-base shadow-2xl ring-1 ring-black ring-opacity-5 focus:outline-none"
      >
        <div class="flex items-center p-1 text-gray-500">
          <Button variant="ghost" class="h-7 w-7" @click="prevMonth">
            <FeatherIcon stroke-width="2" name="chevron-left" class="h-4 w-4" />
          </Button>
          <div class="flex-1 text-center text-base font-medium text-gray-700">
            {{ formatMonth }}
          </div>
          <Button variant="ghost" class="h-7 w-7" @click="nextMonth">
            <FeatherIcon
              stroke-width="2"
              name="chevron-right"
              class="h-4 w-4"
            />
          </Button>
        </div>
        <div class="flex items-center justify-center gap-1 p-1">
          <TextInput
            class="text-sm"
            type="text"
            :value="value"
            @change="
              selectDate(getDate($event.target.value)) || togglePopover()
            "
          />
          <Button
            :label="__('Today')"
            class="text-sm"
            @click="selectDate(getDate()) || togglePopover()"
          />
        </div>
        <div
          class="flex flex-col items-center justify-center p-1 text-gray-800"
        >
          <div class="flex items-center text-xs uppercase">
            <div
              class="flex h-6 w-8 items-center justify-center text-center"
              v-for="(d, i) in ['su', 'mo', 'tu', 'we', 'th', 'fr', 'sa']"
              :key="i"
            >
              {{ __(d) }}
            </div>
          </div>
          <div
            class="flex items-center"
            v-for="(week, i) in datesAsWeeks"
            :key="i"
          >
            <div
              v-for="date in week"
              :key="toValue(date)"
              class="flex h-8 w-8 cursor-pointer items-center justify-center rounded hover:bg-gray-50"
              :class="{
                'text-gray-400': date.getMonth() !== currentMonth - 1,
                'font-extrabold text-gray-900':
                  toValue(date) === toValue(today),
                'bg-gray-800 text-white hover:bg-gray-800':
                  toValue(date) === value,
              }"
              @click="
                () => {
                  selectDate(date)
                  togglePopover()
                }
              "
            >
              {{ __(date.getDate()) }}
            </div>
          </div>
        </div>
        <div class="flex justify-end p-1">
          <Button
            :label="__('Clear')"
            class="text-sm"
            @click="
              () => {
                selectDate('')
                togglePopover()
              }
            "
          />
        </div>
      </div>
    </template>
  </Popover>
</template>

<script>
import { Popover } from 'frappe-ui'
export default {
  name: 'DatePicker',
  props: ['value', 'placeholder', 'formatter', 'readonly', 'inputClass'],
  emits: ['change'],
  components: {
    Popover,
  },
  data() {
    return {
      currentYear: null,
      currentMonth: null,
    }
  },
  created() {
    this.selectCurrentMonthYear()
  },
  computed: {
    today() {
      return this.getDate()
    },
    datesAsWeeks() {
      let datesAsWeeks = []
      let dates = this.dates.slice()
      while (dates.length) {
        let week = dates.splice(0, 7)
        datesAsWeeks.push(week)
      }
      return datesAsWeeks
    },
    dates() {
      if (!(this.currentYear && this.currentMonth)) {
        return []
      }
      let monthIndex = this.currentMonth - 1
      let year = this.currentYear

      let firstDayOfMonth = this.getDate(year, monthIndex, 1)
      let lastDayOfMonth = this.getDate(year, monthIndex + 1, 0)
      let leftPaddingCount = firstDayOfMonth.getDay()
      let rightPaddingCount = 6 - lastDayOfMonth.getDay()

      let leftPadding = this.getDatesAfter(firstDayOfMonth, -leftPaddingCount)
      let rightPadding = this.getDatesAfter(lastDayOfMonth, rightPaddingCount)
      let daysInMonth = this.getDaysInMonth(monthIndex, year)
      let datesInMonth = this.getDatesAfter(firstDayOfMonth, daysInMonth - 1)

      let dates = [
        ...leftPadding,
        firstDayOfMonth,
        ...datesInMonth,
        ...rightPadding,
      ]
      if (dates.length < 42) {
        const finalPadding = this.getDatesAfter(dates.at(-1), 42 - dates.length)
        dates = dates.concat(...finalPadding)
      }
      return dates
    },
    formatMonth() {
      let date = this.getDate(this.currentYear, this.currentMonth - 1, 1)
      let month = __(
        date.toLocaleString('en-US', {
          month: 'long',
        })
      )
      return `${month}, ${date.getFullYear()}`
    },
  },
  methods: {
    selectDate(date) {
      this.$emit('change', this.toValue(date))
    },
    selectCurrentMonthYear() {
      let date = this.value ? this.getDate(this.value) : this.getDate()
      if (date === 'Invalid Date') {
        date = this.getDate()
      }
      this.currentYear = date.getFullYear()
      this.currentMonth = date.getMonth() + 1
    },
    prevMonth() {
      this.changeMonth(-1)
    },
    nextMonth() {
      this.changeMonth(1)
    },
    changeMonth(adder) {
      this.currentMonth = this.currentMonth + adder
      if (this.currentMonth < 1) {
        this.currentMonth = 12
        this.currentYear = this.currentYear - 1
      }
      if (this.currentMonth > 12) {
        this.currentMonth = 1
        this.currentYear = this.currentYear + 1
      }
    },
    getDatesAfter(date, count) {
      let incrementer = 1
      if (count < 0) {
        incrementer = -1
        count = Math.abs(count)
      }
      let dates = []
      while (count) {
        date = this.getDate(
          date.getFullYear(),
          date.getMonth(),
          date.getDate() + incrementer
        )
        dates.push(date)
        count--
      }
      if (incrementer === -1) {
        return dates.reverse()
      }
      return dates
    },

    getDaysInMonth(monthIndex, year) {
      let daysInMonthMap = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
      let daysInMonth = daysInMonthMap[monthIndex]
      if (monthIndex === 1 && this.isLeapYear(year)) {
        return 29
      }
      return daysInMonth
    },

    isLeapYear(year) {
      if (year % 400 === 0) return true
      if (year % 100 === 0) return false
      if (year % 4 === 0) return true
      return false
    },

    toValue(date) {
      if (!date) {
        return ''
      }

      // toISOString is buggy and reduces the day by one
      // this is because it considers the UTC timestamp
      // in order to circumvent that we need to use luxon/moment
      // but that refactor could take some time, so fixing the time difference
      // as suggested in this answer.
      // https://stackoverflow.com/a/16084846/3541205
      date.setHours(0, -date.getTimezoneOffset(), 0, 0)
      return date.toISOString().slice(0, 10)
    },

    getDate(...args) {
      let d = new Date(...args)
      return d
    },
  },
}
</script>
