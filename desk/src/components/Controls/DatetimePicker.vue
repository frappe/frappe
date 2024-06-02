<template>
	<Popover @open="selectCurrentMonthYear" class="flex w-full [&>div:first-child]:w-full">
		<template #target="{ togglePopover }">
			<Input
				readonly
				type="text"
				:placeholder="placeholder"
				:value="value && formatter ? formatter(value) : value"
				@focus="!readonly ? togglePopover() : null"
				:class="inputClass"
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
						<FeatherIcon stroke-width="2" name="chevron-right" class="h-4 w-4" />
					</Button>
				</div>
				<div class="flex items-center justify-center gap-1 p-1">
					<TextInput
						class="text-sm"
						type="text"
						:value="value"
						@change="updateDate($event.target.value) || togglePopover()"
					/>
					<Button
						:label="'Now'"
						class="text-sm"
						@click="selectDate(getDate(), false, true) || togglePopover()"
					/>
				</div>
				<div class="flex flex-col items-center justify-center p-1 text-gray-800">
					<div class="flex items-center text-xs uppercase">
						<div
							class="flex h-6 w-8 items-center justify-center text-center"
							v-for="(d, i) in ['su', 'mo', 'tu', 'we', 'th', 'fr', 'sa']"
							:key="i"
						>
							{{ d }}
						</div>
					</div>
					<div class="flex items-center" v-for="(week, i) in datesAsWeeks" :key="i">
						<div
							v-for="date in week"
							:key="toValue(date)"
							class="flex h-8 w-8 cursor-pointer items-center justify-center rounded hover:bg-gray-50"
							:class="{
								'text-gray-400': date.getMonth() !== currentMonth - 1,
								'font-extrabold text-gray-900': toValue(date) === toValue(today),
								'bg-gray-800 text-white hover:bg-gray-800': toValue(date) === value,
							}"
							@click="
								() => {
									selectDate(date)
									togglePopover()
								}
							"
						>
							{{ date.getDate() }}
						</div>
					</div>
				</div>
				<div class="flex items-center justify-around gap-2 p-1">
					<div>
						{{ twoDigit(hour) }} : {{ twoDigit(minute) }} :
						{{ twoDigit(second) }}
					</div>
					<div class="flex flex-col items-center justify-center">
						<div class="slider flex min-h-4 items-center justify-center">
							<TextInput
								v-model="hour"
								name="hours"
								type="range"
								min="0"
								max="23"
								step="1"
								@change="() => changeTime() || togglePopover()"
							/>
						</div>
						<div class="slider flex min-h-4 items-center justify-center">
							<TextInput
								v-model="minute"
								name="minutes"
								type="range"
								min="0"
								max="59"
								step="1"
								@change="() => changeTime() || togglePopover()"
							/>
						</div>
						<div class="slider flex min-h-4 items-center justify-center">
							<TextInput
								v-model="second"
								name="seconds"
								type="range"
								min="0"
								max="59"
								step="1"
								@change="() => changeTime() || togglePopover()"
							/>
						</div>
					</div>
				</div>
				<div class="flex justify-end p-1">
					<Button
						:label="'Clear'"
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
import { Popover, FeatherIcon, Input, TextInput } from "frappe-ui"
export default {
	name: "DatePicker",
	props: ["value", "placeholder", "formatter", "readonly", "inputClass"],
	emits: ["change"],
	components: {
		Popover,
		FeatherIcon,
		Input,
		TextInput,
	},
	data() {
		return {
			currentYear: null,
			currentMonth: null,
			hour: 0,
			minute: 0,
			second: 0,
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

			let dates = [...leftPadding, firstDayOfMonth, ...datesInMonth, ...rightPadding]
			if (dates.length < 42) {
				const finalPadding = this.getDatesAfter(dates.at(-1), 42 - dates.length)
				dates = dates.concat(...finalPadding)
			}
			return dates
		},
		formatMonth() {
			let date = this.getDate(this.currentYear, this.currentMonth - 1, 1)
			let month = date.toLocaleString("en-US", {
				month: "long",
			})
			return `${month}, ${date.getFullYear()}`
		},
	},
	methods: {
		changeTime() {
			let date = this.value ? this.getDate(this.value) : this.getDate()
			this.selectDate(date, true)
		},
		selectDate(date, isTimeChange = false, isNow = false) {
			if (!isTimeChange) {
				let currentDate = this.value && !isNow ? this.getDate(this.value) : this.getDate()
				this.hour = currentDate.getHours()
				this.minute = currentDate.getMinutes()
				this.second = currentDate.getSeconds()
			}
			this.$emit("change", this.toValue(date))
		},
		selectCurrentMonthYear() {
			let date = this.value ? this.getDate(this.value) : this.getDate()
			if (date === "Invalid Date") {
				date = this.getDate()
			}
			this.currentYear = date.getFullYear()
			this.currentMonth = date.getMonth() + 1
			this.hour = date.getHours()
			this.minute = date.getMinutes()
			this.second = date.getSeconds()
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
				date = this.getDate(date.getFullYear(), date.getMonth(), date.getDate() + incrementer)
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
		twoDigit(number) {
			return number.toString().padStart(2, "0")
		},
		toValue(date) {
			if (!date) return ""

			date.setHours(this.hour, this.minute, this.second, 0)
			// "YYYY-MM-DD HH:MM:SS"
			return `${date.getFullYear()}-${this.twoDigit(date.getMonth() + 1)}-${this.twoDigit(
				date.getDate()
			)} ${this.twoDigit(date.getHours())}:${this.twoDigit(date.getMinutes())}:${this.twoDigit(
				date.getSeconds()
			)}`
		},
		getDate(...args) {
			let d = new Date(...args)
			return d
		},
		updateDate(date) {
			date = this.getDate(date)
			this.hour = date.getHours()
			this.minute = date.getMinutes()
			this.second = date.getSeconds()
			this.selectDate(date, true)
		},
	},
}
</script>

<style scoped>
.slider {
	--trackHeight: 1px;
	--thumbRadius: 10px;
}

:deep(.slider input[type="range"]) {
	-webkit-appearance: none;
	appearance: none;
	height: 100%;
	background: transparent;
	padding: 0;
	margin: 0;
	cursor: pointer;
}

:deep(.slider input[type="range"]::-webkit-slider-runnable-track) {
	appearance: none;
	background: #000;
	height: var(--trackHeight);
	border-radius: 999px;
}

:deep(.slider input[type="range"]:focus-visible) {
	outline: none;
}

:deep(.slider input[type="range"]::-webkit-slider-thumb) {
	width: var(--thumbRadius);
	height: var(--thumbRadius);
	margin-top: calc((var(--trackHeight) - var(--thumbRadius)) / 2);
	background: #fff;
	border-radius: 3px;
	pointer-events: all;
	appearance: none;
	outline: 1px solid #777777;
	z-index: 1;
}

:deep(.slider:hover input[type="range"]::-webkit-slider-thumb) {
	outline: 1px solid #000;
}

:deep(.slider input[type="range"]::-webkit-slider-thumb) {
	width: var(--thumbRadius);
	height: var(--thumbRadius);
	margin-top: calc((var(--trackHeight) - var(--thumbRadius)) / 2);
	background: #fff;
	border-radius: 3px;
	pointer-events: all;
	appearance: none;
	z-index: 1;
}
</style>
