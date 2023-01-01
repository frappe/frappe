/*!
  * Tempus Dominus v6.2.10 (https://getdatepicker.com/)
  * Copyright 2013-2022 Jonathan Peterson
  * Licensed under MIT (https://github.com/Eonasdan/tempus-dominus/blob/master/LICENSE)
  */
(function (global, factory) {
    typeof exports === 'object' && typeof module !== 'undefined' ? factory(exports) :
    typeof define === 'function' && define.amd ? define(['exports'], factory) :
    (global = typeof globalThis !== 'undefined' ? globalThis : global || self, factory(global.tempusDominus = {}));
  })(this, (function (exports) { 'use strict';
  
    exports.Unit = void 0;
    (function (Unit) {
        Unit["seconds"] = "seconds";
        Unit["minutes"] = "minutes";
        Unit["hours"] = "hours";
        Unit["date"] = "date";
        Unit["month"] = "month";
        Unit["year"] = "year";
    })(exports.Unit || (exports.Unit = {}));
    const twoDigitTemplate = {
        month: '2-digit',
        day: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
    };
    const getFormatByUnit = (unit) => {
        switch (unit) {
            case 'date':
                return { dateStyle: 'short' };
            case 'month':
                return {
                    month: 'numeric',
                    year: 'numeric',
                };
            case 'year':
                return { year: 'numeric' };
        }
    };
    const guessHourCycle = (locale) => {
        if (!locale)
            return 'h12';
        // noinspection SpellCheckingInspection
        const template = {
            hour: '2-digit',
            minute: '2-digit',
            numberingSystem: 'latn',
        };
        const dt = new DateTime().setLocale(locale);
        dt.hours = 0;
        const start = dt.parts(undefined, template).hour;
        //midnight is 12 so en-US style 12 AM
        if (start === '12')
            return 'h12';
        //midnight is 24 is from 00-24
        if (start === '24')
            return 'h24';
        dt.hours = 23;
        const end = dt.parts(undefined, template).hour;
        //if midnight is 00 and hour 23 is 11 then
        if (start === '00' && end === '11')
            return 'h11';
        if (start === '00' && end === '23')
            return 'h23';
        console.warn(`couldn't determine hour cycle for ${locale}. start: ${start}. end: ${end}`);
        return undefined;
    };
    /**
     * For the most part this object behaves exactly the same way
     * as the native Date object with a little extra spice.
     */
    class DateTime extends Date {

        constructor() {
            super(...arguments);
            /**
             * Used with Intl.DateTimeFormat
             */
            this.locale = 'default';
            this.nonLeapLadder = [
                0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334,
            ];
            this.leapLadder = [0, 31, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335];
        }
        /**
         * Chainable way to set the {@link locale}
         * @param value
         */
        setLocale(value) {
            this.locale = value;
            return this;
        }
        /**
         * Converts a plain JS date object to a DateTime object.
         * Doing this allows access to format, etc.
         * @param  date
         * @param locale
         */
        static convert(date, locale = 'default') {
            if (!date)
                throw new Error(`A date is required`);
            return new DateTime(date.getFullYear(), date.getMonth(), date.getDate(), date.getHours(), date.getMinutes(), date.getSeconds(), date.getMilliseconds()).setLocale(locale);
        }
        /**
         * Attempts to create a DateTime from a string. A customDateFormat is required for non US dates.
         * @param input
         * @param localization
         */
        //eslint-disable-next-line @typescript-eslint/no-unused-vars
        static fromString(input, localization) {
            return new DateTime(input);
        }
        /**
         * Native date manipulations are not pure functions. This function creates a duplicate of the DateTime object.
         */
        get clone() {
            return new DateTime(this.year, this.month, this.date, this.hours, this.minutes, this.seconds, this.getMilliseconds()).setLocale(this.locale);
        }
        /**
         * Sets the current date to the start of the {@link unit} provided
         * Example: Consider a date of "April 30, 2021, 11:45:32.984 AM" => new DateTime(2021, 3, 30, 11, 45, 32, 984).startOf('month')
         * would return April 1, 2021, 12:00:00.000 AM (midnight)
         * @param unit
         * @param startOfTheWeek Allows for the changing the start of the week.
         */
        startOf(unit, startOfTheWeek = 0) {
            if (this[unit] === undefined)
                throw new Error(`Unit '${unit}' is not valid`);
            switch (unit) {
                case 'seconds':
                    this.setMilliseconds(0);
                    break;
                case 'minutes':
                    this.setSeconds(0, 0);
                    break;
                case 'hours':
                    this.setMinutes(0, 0, 0);
                    break;
                case 'date':
                    this.setHours(0, 0, 0, 0);
                    break;
                case 'weekDay': {
                    this.startOf(exports.Unit.date);
                    if (this.weekDay === startOfTheWeek)
                        break;
                    let goBack = this.weekDay;
                    if (startOfTheWeek !== 0 && this.weekDay === 0)
                        goBack = 8 - startOfTheWeek;
                    this.manipulate(startOfTheWeek - goBack, exports.Unit.date);
                    break;
                }
                case 'month':
                    this.startOf(exports.Unit.date);
                    this.setDate(1);
                    break;
                case 'year':
                    this.startOf(exports.Unit.date);
                    this.setMonth(0, 1);
                    break;
            }
            return this;
        }
        /**
         * Sets the current date to the end of the {@link unit} provided
         * Example: Consider a date of "April 30, 2021, 11:45:32.984 AM" => new DateTime(2021, 3, 30, 11, 45, 32, 984).endOf('month')
         * would return April 30, 2021, 11:59:59.999 PM
         * @param unit
         * @param startOfTheWeek
         */
        endOf(unit, startOfTheWeek = 0) {
            if (this[unit] === undefined)
                throw new Error(`Unit '${unit}' is not valid`);
            switch (unit) {
                case 'seconds':
                    this.setMilliseconds(999);
                    break;
                case 'minutes':
                    this.setSeconds(59, 999);
                    break;
                case 'hours':
                    this.setMinutes(59, 59, 999);
                    break;
                case 'date':
                    this.setHours(23, 59, 59, 999);
                    break;
                case 'weekDay': {
                    this.endOf(exports.Unit.date);
                    const endOfWeek = 6 + startOfTheWeek;
                    if (this.weekDay === endOfWeek)
                        break;
                    this.manipulate(endOfWeek - this.weekDay, exports.Unit.date);
                    break;
                }
                case 'month':
                    this.endOf(exports.Unit.date);
                    this.manipulate(1, exports.Unit.month);
                    this.setDate(0);
                    break;
                case 'year':
                    this.endOf(exports.Unit.date);
                    this.setMonth(11, 31);
                    break;
            }
            return this;
        }
        /**
         * Change a {@link unit} value. Value can be positive or negative
         * Example: Consider a date of "April 30, 2021, 11:45:32.984 AM" => new DateTime(2021, 3, 30, 11, 45, 32, 984).manipulate(1, 'month')
         * would return May 30, 2021, 11:45:32.984 AM
         * @param value A positive or negative number
         * @param unit
         */
        manipulate(value, unit) {
            if (this[unit] === undefined)
                throw new Error(`Unit '${unit}' is not valid`);
            this[unit] += value;
            return this;
        }
        /**
         * Returns a string format.
         * See https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/DateTimeFormat
         * for valid templates and locale objects
         * @param template An object. Uses browser defaults otherwise.
         * @param locale Can be a string or an array of strings. Uses browser defaults otherwise.
         */
        format(template, locale = this.locale) {
            return new Intl.DateTimeFormat(locale, template).format(this);
        }
        /**
         * Return true if {@link compare} is before this date
         * @param compare The Date/DateTime to compare
         * @param unit If provided, uses {@link startOf} for
         * comparision.
         */
        isBefore(compare, unit) {
            if (!unit)
                return this.valueOf() < compare.valueOf();
            if (this[unit] === undefined)
                throw new Error(`Unit '${unit}' is not valid`);
            return (this.clone.startOf(unit).valueOf() < compare.clone.startOf(unit).valueOf());
        }
        /**
         * Return true if {@link compare} is after this date
         * @param compare The Date/DateTime to compare
         * @param unit If provided, uses {@link startOf} for
         * comparision.
         */
        isAfter(compare, unit) {
            if (!unit)
                return this.valueOf() > compare.valueOf();
            if (this[unit] === undefined)
                throw new Error(`Unit '${unit}' is not valid`);
            return (this.clone.startOf(unit).valueOf() > compare.clone.startOf(unit).valueOf());
        }
        /**
         * Return true if {@link compare} is same this date
         * @param compare The Date/DateTime to compare
         * @param unit If provided, uses {@link startOf} for
         * comparision.
         */
        isSame(compare, unit) {
            if (!unit)
                return this.valueOf() === compare.valueOf();
            if (this[unit] === undefined)
                throw new Error(`Unit '${unit}' is not valid`);
            compare = DateTime.convert(compare);
            return (this.clone.startOf(unit).valueOf() === compare.startOf(unit).valueOf());
        }
        /**
         * Check if this is between two other DateTimes, optionally looking at unit scale. The match is exclusive.
         * @param left
         * @param right
         * @param unit.
         * @param inclusivity. A [ indicates inclusion of a value. A ( indicates exclusion.
         * If the inclusivity parameter is used, both indicators must be passed.
         */
        isBetween(left, right, unit, inclusivity = '()') {
            if (unit && this[unit] === undefined)
                throw new Error(`Unit '${unit}' is not valid`);
            const leftInclusivity = inclusivity[0] === '(';
            const rightInclusivity = inclusivity[1] === ')';
            return (((leftInclusivity
                ? this.isAfter(left, unit)
                : !this.isBefore(left, unit)) &&
                (rightInclusivity
                    ? this.isBefore(right, unit)
                    : !this.isAfter(right, unit))) ||
                ((leftInclusivity
                    ? this.isBefore(left, unit)
                    : !this.isAfter(left, unit)) &&
                    (rightInclusivity
                        ? this.isAfter(right, unit)
                        : !this.isBefore(right, unit))));
        }
        /**
         * Returns flattened object of the date. Does not include literals
         * @param locale
         * @param template
         */
        parts(locale = this.locale, template = { dateStyle: 'full', timeStyle: 'long' }) {
            const parts = {};
            new Intl.DateTimeFormat(locale, template)
                .formatToParts(this)
                .filter((x) => x.type !== 'literal')
                .forEach((x) => (parts[x.type] = x.value));
            return parts;
        }
        /**
         * Shortcut to Date.getSeconds()
         */
        get seconds() {
            return this.getSeconds();
        }
        /**
         * Shortcut to Date.setSeconds()
         */
        set seconds(value) {
            this.setSeconds(value);
        }
        /**
         * Returns two digit hours
         */
        get secondsFormatted() {
            return this.parts(undefined, twoDigitTemplate).second;
        }
        /**
         * Shortcut to Date.getMinutes()
         */
        get minutes() {
            return this.getMinutes();
        }
        /**
         * Shortcut to Date.setMinutes()
         */
        set minutes(value) {
            this.setMinutes(value);
        }
        /**
         * Returns two digit minutes
         */
        get minutesFormatted() {
            return this.parts(undefined, twoDigitTemplate).minute;
        }
        /**
         * Shortcut to Date.getHours()
         */
        get hours() {
            return this.getHours();
        }
        /**
         * Shortcut to Date.setHours()
         */
        set hours(value) {
            this.setHours(value);
        }
        getHoursFormatted(hourCycle = 'h12') {
            return this.parts(undefined, { ...twoDigitTemplate, hourCycle: hourCycle })
                .hour;
        }
        /**
         * Get the meridiem of the date. E.g. AM or PM.
         * If the {@link locale} provides a "dayPeriod" then this will be returned,
         * otherwise it will return AM or PM.
         * @param locale
         */
        meridiem(locale = this.locale) {
            return new Intl.DateTimeFormat(locale, {
                hour: 'numeric',
                hour12: true,
            })
                .formatToParts(this)
                .find((p) => p.type === 'dayPeriod')?.value;
        }
        /**
         * Shortcut to Date.getDate()
         */
        get date() {
            return this.getDate();
        }
        /**
         * Shortcut to Date.setDate()
         */
        set date(value) {
            this.setDate(value);
        }
        /**
         * Return two digit date
         */
        get dateFormatted() {
            return this.parts(undefined, twoDigitTemplate).day;
        }
        /**
         * Shortcut to Date.getDay()
         */
        get weekDay() {
            return this.getDay();
        }
        /**
         * Shortcut to Date.getMonth()
         */
        get month() {
            return this.getMonth();
        }
        /**
         * Shortcut to Date.setMonth()
         */
        set month(value) {
            const targetMonth = new Date(this.year, value + 1);
            targetMonth.setDate(0);
            const endOfMonth = targetMonth.getDate();
            if (this.date > endOfMonth) {
                this.date = endOfMonth;
            }
            this.setMonth(value);
        }
        /**
         * Return two digit, human expected month. E.g. January = 1, December = 12
         */
        get monthFormatted() {
            return this.parts(undefined, twoDigitTemplate).month;
        }
        /**
         * Shortcut to Date.getFullYear()
         */
        get year() {
            return this.getFullYear();
        }
        /**
         * Shortcut to Date.setFullYear()
         */
        set year(value) {
            this.setFullYear(value);
        }
        // borrowed a bunch of stuff from Luxon
        /**
         * Gets the week of the year
         */
        get week() {
            const ordinal = this.computeOrdinal(), weekday = this.getUTCDay();
            let weekNumber = Math.floor((ordinal - weekday + 10) / 7);
            if (weekNumber < 1) {
                weekNumber = this.weeksInWeekYear(this.year - 1);
            }
            else if (weekNumber > this.weeksInWeekYear(this.year)) {
                weekNumber = 1;
            }
            return weekNumber;
        }
        weeksInWeekYear(weekYear) {
            const p1 = (weekYear +
                Math.floor(weekYear / 4) -
                Math.floor(weekYear / 100) +
                Math.floor(weekYear / 400)) %
                7, last = weekYear - 1, p2 = (last +
                Math.floor(last / 4) -
                Math.floor(last / 100) +
                Math.floor(last / 400)) %
                7;
            return p1 === 4 || p2 === 3 ? 53 : 52;
        }
        get isLeapYear() {
            return (this.year % 4 === 0 && (this.year % 100 !== 0 || this.year % 400 === 0));
        }
        computeOrdinal() {
            return (this.date +
                (this.isLeapYear ? this.leapLadder : this.nonLeapLadder)[this.month]);
        }
    }
  
    class TdError extends Error {
    }
    class ErrorMessages {
        constructor() {
            this.base = 'TD:';
            //#endregion
            //#region used with notify.error
            /**
             * Used with an Error Event type if the user selects a date that
             * fails restriction validation.
             */
            this.failedToSetInvalidDate = 'Failed to set invalid date';
            /**
             * Used with an Error Event type when a user changes the value of the
             * input field directly, and does not provide a valid date.
             */
            this.failedToParseInput = 'Failed parse input field';
            //#endregion
        }
        //#region out to console
        /**
         * Throws an error indicating that a key in the options object is invalid.
         * @param optionName
         */
        unexpectedOption(optionName) {
            const error = new TdError(`${this.base} Unexpected option: ${optionName} does not match a known option.`);
            error.code = 1;
            throw error;
        }
        /**
         * Throws an error indicating that one more keys in the options object is invalid.
         * @param optionName
         */
        unexpectedOptions(optionName) {
            const error = new TdError(`${this.base}: ${optionName.join(', ')}`);
            error.code = 1;
            throw error;
        }
        /**
         * Throws an error when an option is provide an unsupported value.
         * For example a value of 'cheese' for toolbarPlacement which only supports
         * 'top', 'bottom', 'default'.
         * @param optionName
         * @param badValue
         * @param validOptions
         */
        unexpectedOptionValue(optionName, badValue, validOptions) {
            const error = new TdError(`${this.base} Unexpected option value: ${optionName} does not accept a value of "${badValue}". Valid values are: ${validOptions.join(', ')}`);
            error.code = 2;
            throw error;
        }
        /**
         * Throws an error when an option value is the wrong type.
         * For example a string value was provided to multipleDates which only
         * supports true or false.
         * @param optionName
         * @param badType
         * @param expectedType
         */
        typeMismatch(optionName, badType, expectedType) {
            const error = new TdError(`${this.base} Mismatch types: ${optionName} has a type of ${badType} instead of the required ${expectedType}`);
            error.code = 3;
            throw error;
        }
        /**
         * Throws an error when an option value is  outside of the expected range.
         * For example restrictions.daysOfWeekDisabled excepts a value between 0 and 6.
         * @param optionName
         * @param lower
         * @param upper
         */
        numbersOutOfRange(optionName, lower, upper) {
            const error = new TdError(`${this.base} ${optionName} expected an array of number between ${lower} and ${upper}.`);
            error.code = 4;
            throw error;
        }
        /**
         * Throws an error when a value for a date options couldn't be parsed. Either
         * the option was an invalid string or an invalid Date object.
         * @param optionName
         * @param date
         * @param soft If true, logs a warning instead of an error.
         */
        //eslint-disable-next-line @typescript-eslint/no-explicit-any
        failedToParseDate(optionName, date, soft = false) {
            const error = new TdError(`${this.base} Could not correctly parse "${date}" to a date for ${optionName}.`);
            error.code = 5;
            if (!soft)
                throw error;
            console.warn(error);
        }
        /**
         * Throws when an element to attach to was not provided in the constructor.
         */
        mustProvideElement() {
            const error = new TdError(`${this.base} No element was provided.`);
            error.code = 6;
            throw error;
        }
        /**
         * Throws if providing an array for the events to subscribe method doesn't have
         * the same number of callbacks. E.g., subscribe([1,2], [1])
         */
        subscribeMismatch() {
            const error = new TdError(`${this.base} The subscribed events does not match the number of callbacks`);
            error.code = 7;
            throw error;
        }
        /**
         * Throws if the configuration has conflicting rules e.g. minDate is after maxDate
         */
        conflictingConfiguration(message) {
            const error = new TdError(`${this.base} A configuration value conflicts with another rule. ${message}`);
            error.code = 8;
            throw error;
        }
        /**
         * customDateFormat errors
         */
        customDateFormatError(message) {
            const error = new TdError(`${this.base} customDateFormat: ${message}`);
            error.code = 9;
            throw error;
        }
        /**
         * Logs a warning if a date option value is provided as a string, instead of
         * a date/datetime object.
         */
        dateString() {
            console.warn(`${this.base} Using a string for date options is not recommended unless you specify an ISO string or use the customDateFormat plugin.`);
        }
        deprecatedWarning(message, remediation) {
            console.warn(`${this.base} Warning ${message} is deprecated and will be removed in a future version. ${remediation}`);
        }
        throwError(message) {
            const error = new TdError(`${this.base} ${message}`);
            error.code = 9;
            throw error;
        }
    }
  
    // this is not the way I want this to stay but nested classes seemed to blown up once its compiled.
    const NAME = 'tempus-dominus', dataKey = 'td';
    /**
     * Events
     */
    class Events {
        constructor() {
            this.key = `.${dataKey}`;
            /**
             * Change event. Fired when the user selects a date.
             * See also EventTypes.ChangeEvent
             */
            this.change = `change${this.key}`;
            /**
             * Emit when the view changes for example from month view to the year view.
             * See also EventTypes.ViewUpdateEvent
             */
            this.update = `update${this.key}`;
            /**
             * Emits when a selected date or value from the input field fails to meet the provided validation rules.
             * See also EventTypes.FailEvent
             */
            this.error = `error${this.key}`;
            /**
             * Show event
             * @event Events#show
             */
            this.show = `show${this.key}`;
            /**
             * Hide event
             * @event Events#hide
             */
            this.hide = `hide${this.key}`;
            // blur and focus are used in the jQuery provider but are otherwise unused.
            // keyup/down will be used later for keybinding options
            this.blur = `blur${this.key}`;
            this.focus = `focus${this.key}`;
            this.keyup = `keyup${this.key}`;
            this.keydown = `keydown${this.key}`;
        }
    }
    class Css {
        constructor() {
            /**
             * The outer element for the widget.
             */
            this.widget = `${NAME}-widget`;
            /**
             * Hold the previous, next and switcher divs
             */
            this.calendarHeader = 'calendar-header';
            /**
             * The element for the action to change the calendar view. E.g. month -> year.
             */
            this.switch = 'picker-switch';
            /**
             * The elements for all the toolbar options
             */
            this.toolbar = 'toolbar';
            /**
             * Disables the hover and rounding affect.
             */
            this.noHighlight = 'no-highlight';
            /**
             * Applied to the widget element when the side by side option is in use.
             */
            this.sideBySide = 'timepicker-sbs';
            /**
             * The element for the action to change the calendar view, e.g. August -> July
             */
            this.previous = 'previous';
            /**
             * The element for the action to change the calendar view, e.g. August -> September
             */
            this.next = 'next';
            /**
             * Applied to any action that would violate any restriction options. ALso applied
             * to an input field if the disabled function is called.
             */
            this.disabled = 'disabled';
            /**
             * Applied to any date that is less than requested view,
             * e.g. the last day of the previous month.
             */
            this.old = 'old';
            /**
             * Applied to any date that is greater than of requested view,
             * e.g. the last day of the previous month.
             */
            this.new = 'new';
            /**
             * Applied to any date that is currently selected.
             */
            this.active = 'active';
            this.btn = 'btn-primary'
            //#region date element
            /**
             * The outer element for the calendar view.
             */
            this.dateContainer = 'date-container';
            /**
             * The outer element for the decades view.
             */
            this.decadesContainer = `${this.dateContainer}-decades`;
            /**
             * Applied to elements within the decades container, e.g. 2020, 2030
             */
            this.decade = 'decade';
            /**
             * The outer element for the years view.
             */
            this.yearsContainer = `${this.dateContainer}-years`;
            /**
             * Applied to elements within the years container, e.g. 2021, 2021
             */
            this.year = 'year';
            /**
             * The outer element for the month view.
             */
            this.monthsContainer = `${this.dateContainer}-months`;
            /**
             * Applied to elements within the month container, e.g. January, February
             */
            this.month = 'month';
            /**
             * The outer element for the calendar view.
             */
            this.daysContainer = `${this.dateContainer}-days`;
            /**
             * Applied to elements within the day container, e.g. 1, 2..31
             */
            this.day = 'day';
            /**
             * If display.calendarWeeks is enabled, a column displaying the week of year
             * is shown. This class is applied to each cell in that column.
             */
            this.calendarWeeks = 'cw';
            /**
             * Applied to the first row of the calendar view, e.g. Sunday, Monday
             */
            this.dayOfTheWeek = 'dow';
            /**
             * Applied to the current date on the calendar view.
             */
            this.today = 'today';
            /**
             * Applied to the locale's weekend dates on the calendar view, e.g. Sunday, Saturday
             */
            this.weekend = 'weekend';
            //#endregion
            //#region time element
            /**
             * The outer element for all time related elements.
             */
            this.timeContainer = 'time-container';
            /**
             * Applied the separator columns between time elements, e.g. hour *:* minute *:* second
             */
            this.separator = 'separator';
            /**
             * The outer element for the clock view.
             */
            this.clockContainer = `${this.timeContainer}-clock`;
            /**
             * The outer element for the hours selection view.
             */
            this.hourContainer = `${this.timeContainer}-hour`;
            /**
             * The outer element for the minutes selection view.
             */
            this.minuteContainer = `${this.timeContainer}-minute`;
            /**
             * The outer element for the seconds selection view.
             */
            this.secondContainer = `${this.timeContainer}-second`;
            /**
             * Applied to each element in the hours selection view.
             */
            this.hour = 'hour';
            /**
             * Applied to each element in the minutes selection view.
             */
            this.minute = 'minute';
            /**
             * Applied to each element in the seconds selection view.
             */
            this.second = 'second';
            /**
             * Applied AM/PM toggle button.
             */
            this.toggleMeridiem = 'toggleMeridiem';
            //#endregion
            //#region collapse
            /**
             * Applied the element of the current view mode, e.g. calendar or clock.
             */
            this.show = 'show';
            /**
             * Applied to the currently showing view mode during a transition
             * between calendar and clock views
             */
            this.collapsing = 'td-collapsing';
            /**
             * Applied to the currently hidden view mode.
             */
            this.collapse = 'td-collapse';
            //#endregion
            /**
             * Applied to the widget when the option display.inline is enabled.
             */
            this.inline = 'inline';
            /**
             * Applied to the widget when the option display.theme is light.
             */
            this.lightTheme = 'light';
            /**
             * Applied to the widget when the option display.theme is dark.
             */
            this.darkTheme = 'dark';
            /**
             * Used for detecting if the system color preference is dark mode
             */
            this.isDarkPreferredQuery = '(prefers-color-scheme: dark)';
        }
    }
    class Namespace {
    }
    Namespace.NAME = NAME;
    // noinspection JSUnusedGlobalSymbols
    Namespace.dataKey = dataKey;
    Namespace.events = new Events();
    Namespace.css = new Css();
    Namespace.errorMessages = new ErrorMessages();
  
    class ServiceLocator {
        constructor() {
            this.cache = new Map();
        }
        locate(identifier) {
            const service = this.cache.get(identifier);
            if (service)
                return service;
            const value = new identifier();
            this.cache.set(identifier, value);
            return value;
        }
    }
    const setupServiceLocator = () => {
        serviceLocator = new ServiceLocator();
    };
    let serviceLocator;
  
    const CalendarModes = [
        {
            name: 'calendar',
            className: Namespace.css.daysContainer,
            unit: exports.Unit.month,
            step: 1,
        },
        {
            name: 'months',
            className: Namespace.css.monthsContainer,
            unit: exports.Unit.year,
            step: 1,
        },
        {
            name: 'years',
            className: Namespace.css.yearsContainer,
            unit: exports.Unit.year,
            step: 10,
        },
        {
            name: 'decades',
            className: Namespace.css.decadesContainer,
            unit: exports.Unit.year,
            step: 100,
        },
    ];
  
    class OptionsStore {
        constructor() {
            this._currentCalendarViewMode = 0;
            this._viewDate = new DateTime();
            this.minimumCalendarViewMode = 0;
            this.currentView = 'calendar';
        }
        get currentCalendarViewMode() {
            return this._currentCalendarViewMode;
        }
        set currentCalendarViewMode(value) {
            this._currentCalendarViewMode = value;
            this.currentView = CalendarModes[value].name;
        }
        get viewDate() {
            return this._viewDate;
        }
        set viewDate(v) {
            this._viewDate = v;
            if (this.options)
                this.options.viewDate = v;
        }
        /**
         * When switching back to the calendar from the clock,
         * this sets currentView to the correct calendar view.
         */
        refreshCurrentView() {
            this.currentView = CalendarModes[this.currentCalendarViewMode].name;
        }
        get isTwelveHour() {
            return ['h12', 'h11'].includes(this.options.localization.hourCycle);
        }
    }
  
    /**
     * Main class for date validation rules based on the options provided.
     */
    class Validation {
        constructor() {
            this.optionsStore = serviceLocator.locate(OptionsStore);
        }
        /**
         * Checks to see if the target date is valid based on the rules provided in the options.
         * Granularity can be provided to check portions of the date instead of the whole.
         * @param targetDate
         * @param granularity
         */
        isValid(targetDate, granularity) {
            if (granularity !== exports.Unit.month &&
                this.optionsStore.options.restrictions.disabledDates.length > 0 &&
                this._isInDisabledDates(targetDate)) {
                return false;
            }
            if (granularity !== exports.Unit.month &&
                this.optionsStore.options.restrictions.enabledDates.length > 0 &&
                !this._isInEnabledDates(targetDate)) {
                return false;
            }
            if (granularity !== exports.Unit.month &&
                granularity !== exports.Unit.year &&
                this.optionsStore.options.restrictions.daysOfWeekDisabled?.length > 0 &&
                this.optionsStore.options.restrictions.daysOfWeekDisabled.indexOf(targetDate.weekDay) !== -1) {
                return false;
            }
            if (this.optionsStore.options.restrictions.minDate &&
                targetDate.isBefore(this.optionsStore.options.restrictions.minDate, granularity)) {
                return false;
            }
            if (this.optionsStore.options.restrictions.maxDate &&
                targetDate.isAfter(this.optionsStore.options.restrictions.maxDate, granularity)) {
                return false;
            }
            if (granularity === exports.Unit.hours ||
                granularity === exports.Unit.minutes ||
                granularity === exports.Unit.seconds) {
                if (this.optionsStore.options.restrictions.disabledHours.length > 0 &&
                    this._isInDisabledHours(targetDate)) {
                    return false;
                }
                if (this.optionsStore.options.restrictions.enabledHours.length > 0 &&
                    !this._isInEnabledHours(targetDate)) {
                    return false;
                }
                if (this.optionsStore.options.restrictions.disabledTimeIntervals.length > 0) {
                    for (const disabledTimeIntervals of this.optionsStore.options
                        .restrictions.disabledTimeIntervals) {
                        if (targetDate.isBetween(disabledTimeIntervals.from, disabledTimeIntervals.to))
                            return false;
                    }
                }
            }
            return true;
        }
        /**
         * Checks to see if the disabledDates option is in use and returns true (meaning invalid)
         * if the `testDate` is with in the array. Granularity is by date.
         * @param testDate
         * @private
         */
        _isInDisabledDates(testDate) {
            if (!this.optionsStore.options.restrictions.disabledDates ||
                this.optionsStore.options.restrictions.disabledDates.length === 0)
                return false;
            return this.optionsStore.options.restrictions.disabledDates.find((x) => x.isSame(testDate, exports.Unit.date));
        }
        /**
         * Checks to see if the enabledDates option is in use and returns true (meaning valid)
         * if the `testDate` is with in the array. Granularity is by date.
         * @param testDate
         * @private
         */
        _isInEnabledDates(testDate) {
            if (!this.optionsStore.options.restrictions.enabledDates ||
                this.optionsStore.options.restrictions.enabledDates.length === 0)
                return true;
            return this.optionsStore.options.restrictions.enabledDates.find((x) => x.isSame(testDate, exports.Unit.date));
        }
        /**
         * Checks to see if the disabledHours option is in use and returns true (meaning invalid)
         * if the `testDate` is with in the array. Granularity is by hours.
         * @param testDate
         * @private
         */
        _isInDisabledHours(testDate) {
            if (!this.optionsStore.options.restrictions.disabledHours ||
                this.optionsStore.options.restrictions.disabledHours.length === 0)
                return false;
            const formattedDate = testDate.hours;
            return this.optionsStore.options.restrictions.disabledHours.find((x) => x === formattedDate);
        }
        /**
         * Checks to see if the enabledHours option is in use and returns true (meaning valid)
         * if the `testDate` is with in the array. Granularity is by hours.
         * @param testDate
         * @private
         */
        _isInEnabledHours(testDate) {
            if (!this.optionsStore.options.restrictions.enabledHours ||
                this.optionsStore.options.restrictions.enabledHours.length === 0)
                return true;
            const formattedDate = testDate.hours;
            return this.optionsStore.options.restrictions.enabledHours.find((x) => x === formattedDate);
        }
    }
  
    class EventEmitter {
        constructor() {
            this.subscribers = [];
        }
        subscribe(callback) {
            this.subscribers.push(callback);
            return this.unsubscribe.bind(this, this.subscribers.length - 1);
        }
        unsubscribe(index) {
            this.subscribers.splice(index, 1);
        }
        emit(value) {
            this.subscribers.forEach((callback) => {
                callback(value);
            });
        }
        destroy() {
            this.subscribers = null;
            this.subscribers = [];
        }
    }
    class EventEmitters {
        constructor() {
            this.triggerEvent = new EventEmitter();
            this.viewUpdate = new EventEmitter();
            this.updateDisplay = new EventEmitter();
            this.action = new EventEmitter(); //eslint-disable-line @typescript-eslint/no-explicit-any
            this.updateViewDate = new EventEmitter();
        }
        destroy() {
            this.triggerEvent.destroy();
            this.viewUpdate.destroy();
            this.updateDisplay.destroy();
            this.action.destroy();
            this.updateViewDate.destroy();
        }
    }
  
    const DefaultOptions = {
        restrictions: {
            minDate: undefined,
            maxDate: undefined,
            disabledDates: [],
            enabledDates: [],
            daysOfWeekDisabled: [],
            disabledTimeIntervals: [],
            disabledHours: [],
            enabledHours: [],
        },
        display: {
            icons: {
                type: 'icons',
                time: 'fa-solid fa-clock',
                date: 'fa-solid fa-calendar',
                up: 'fa-solid fa-arrow-up',
                down: 'fa-solid fa-arrow-down',
                previous: 'fa-solid fa-chevron-left',
                next: 'fa-solid fa-chevron-right',
                today: 'fa-solid fa-calendar-check',
                clear: 'fa-solid fa-trash',
                close: 'fa-solid fa-xmark',
            },
            sideBySide: false,
            calendarWeeks: false,
            viewMode: 'calendar',
            toolbarPlacement: 'bottom',
            keepOpen: false,
            buttons: {
                today: false,
                clear: false,
                close: false,
            },
            components: {
                calendar: true,
                date: true,
                month: true,
                year: true,
                decades: true,
                clock: true,
                hours: true,
                minutes: true,
                seconds: false,
                useTwentyfourHour: undefined,
            },
            inline: false,
            theme: 'auto',
        },
        stepping: 1,
        useCurrent: true,
        defaultDate: undefined,
        localization: {
            today: 'Go to today',
            clear: 'Clear selection',
            close: 'Close the picker',
            selectMonth: 'Select Month',
            previousMonth: 'Previous Month',
            nextMonth: 'Next Month',
            selectYear: 'Select Year',
            previousYear: 'Previous Year',
            nextYear: 'Next Year',
            selectDecade: 'Select Decade',
            previousDecade: 'Previous Decade',
            nextDecade: 'Next Decade',
            previousCentury: 'Previous Century',
            nextCentury: 'Next Century',
            pickHour: 'Pick Hour',
            incrementHour: 'Increment Hour',
            decrementHour: 'Decrement Hour',
            pickMinute: 'Pick Minute',
            incrementMinute: 'Increment Minute',
            decrementMinute: 'Decrement Minute',
            pickSecond: 'Pick Second',
            incrementSecond: 'Increment Second',
            decrementSecond: 'Decrement Second',
            toggleMeridiem: 'Toggle Meridiem',
            selectTime: 'Select Time',
            selectDate: 'Select Date',
            dayViewHeaderFormat: { month: 'long', year: '2-digit' },
            locale: 'default',
            hourCycle: undefined,
            startOfTheWeek: 0,
            /**
             * This is only used with the customDateFormat plugin
             */
            dateFormats: {
                LTS: 'h:mm:ss T',
                LT: 'h:mm T',
                L: 'MM/dd/yyyy',
                LL: 'MMMM d, yyyy',
                LLL: 'MMMM d, yyyy h:mm T',
                LLLL: 'dddd, MMMM d, yyyy h:mm T',
            },
            /**
             * This is only used with the customDateFormat plugin
             */
            ordinal: (n) => n,
            /**
             * This is only used with the customDateFormat plugin
             */
            format: 'L LT',
        },
        keepInvalid: false,
        debug: false,
        allowInputToggle: false,
        viewDate: new DateTime(),
        multipleDates: false,
        multipleDatesSeparator: '; ',
        promptTimeOnDateChange: false,
        promptTimeOnDateChangeTransitionDelay: 200,
        meta: {},
        container: undefined,
    };
  
    /**
     * Attempts to prove `d` is a DateTime or Date or can be converted into one.
     * @param d If a string will attempt creating a date from it.
     * @param localization object containing locale and format settings. Only used with the custom formats
     * @private
     */
    function tryConvertToDateTime(d, localization) {
        if (d.constructor.name === DateTime.name)
            return d;
        if (d.constructor.name === Date.name) {
            return DateTime.convert(d);
        }
        if (typeof d === typeof '') {
            const dateTime = DateTime.fromString(d, localization);
            if (JSON.stringify(dateTime) === 'null') {
                return null;
            }
            return dateTime;
        }
        return null;
    }
    /**
     * Attempts to convert `d` to a DateTime object
     * @param d value to convert
     * @param optionName Provides text to error messages e.g. disabledDates
     * @param localization object containing locale and format settings. Only used with the custom formats
     */
    function convertToDateTime(d, optionName, localization) {
        if (typeof d === typeof '' && optionName !== 'input') {
            Namespace.errorMessages.dateString();
        }
        const converted = tryConvertToDateTime(d, localization);
        if (!converted) {
            Namespace.errorMessages.failedToParseDate(optionName, d, optionName === 'input');
        }
        return converted;
    }
    /**
     * Type checks that `value` is an array of Date or DateTime
     * @param optionName Provides text to error messages e.g. disabledDates
     * @param value Option value
     * @param providedType Used to provide text to error messages
     * @param localization
     */
    function typeCheckDateArray(optionName, value, //eslint-disable-line @typescript-eslint/no-explicit-any
    providedType, localization) {
        if (!Array.isArray(value)) {
            Namespace.errorMessages.typeMismatch(optionName, providedType, 'array of DateTime or Date');
        }
        for (let i = 0; i < value.length; i++) {
            const d = value[i];
            const dateTime = convertToDateTime(d, optionName, localization);
            if (!dateTime) {
                Namespace.errorMessages.typeMismatch(optionName, typeof d, 'DateTime or Date');
            }
            dateTime.setLocale(localization?.locale ?? 'default');
            value[i] = dateTime;
        }
    }
    /**
     * Type checks that `value` is an array of numbers
     * @param optionName Provides text to error messages e.g. disabledDates
     * @param value Option value
     * @param providedType Used to provide text to error messages
     */
    function typeCheckNumberArray(optionName, value, //eslint-disable-line @typescript-eslint/no-explicit-any
    providedType) {
        if (!Array.isArray(value) || value.some((x) => typeof x !== typeof 0)) {
            Namespace.errorMessages.typeMismatch(optionName, providedType, 'array of numbers');
        }
    }
  
    function mandatoryDate(key) {
        return ({ value, providedType, localization }) => {
            const dateTime = convertToDateTime(value, key, localization);
            if (dateTime !== undefined) {
                dateTime.setLocale(localization.locale);
                return dateTime;
            }
            Namespace.errorMessages.typeMismatch(key, providedType, 'DateTime or Date');
        };
    }
    function optionalDate(key) {
        const mandatory = mandatoryDate(key);
        return (args) => {
            if (args.value === undefined) {
                return args.value;
            }
            return mandatory(args);
        };
    }
    function numbersInRange(key, lower, upper) {
        return ({ value, providedType }) => {
            if (value === undefined) {
                return [];
            }
            typeCheckNumberArray(key, value, providedType);
            if (value.some((x) => x < lower || x > upper))
                Namespace.errorMessages.numbersOutOfRange(key, lower, upper);
            return value;
        };
    }
    function validHourRange(key) {
        return numbersInRange(key, 0, 23);
    }
    function validDateArray(key) {
        return ({ value, providedType, localization }) => {
            if (value === undefined) {
                return [];
            }
            typeCheckDateArray(key, value, providedType, localization);
            return value;
        };
    }
    function validKeyOption(keyOptions) {
        return ({ value, path }) => {
            if (!keyOptions.includes(value))
                Namespace.errorMessages.unexpectedOptionValue(path.substring(1), value, keyOptions);
            return value;
        };
    }
    const optionProcessors = Object.freeze({
        defaultDate: mandatoryDate('defaultDate'),
        viewDate: mandatoryDate('viewDate'),
        minDate: optionalDate('restrictions.minDate'),
        maxDate: optionalDate('restrictions.maxDate'),
        disabledHours: validHourRange('restrictions.disabledHours'),
        enabledHours: validHourRange('restrictions.enabledHours'),
        disabledDates: validDateArray('restrictions.disabledDates'),
        enabledDates: validDateArray('restrictions.enabledDates'),
        daysOfWeekDisabled: numbersInRange('restrictions.daysOfWeekDisabled', 0, 6),
        disabledTimeIntervals: ({ key, value, providedType, localization }) => {
            if (value === undefined) {
                return [];
            }
            if (!Array.isArray(value)) {
                Namespace.errorMessages.typeMismatch(key, providedType, 'array of { from: DateTime|Date, to: DateTime|Date }');
            }
            const valueObject = value; //eslint-disable-line @typescript-eslint/no-explicit-any
            for (let i = 0; i < valueObject.length; i++) {
                Object.keys(valueObject[i]).forEach((vk) => {
                    const subOptionName = `${key}[${i}].${vk}`;
                    const d = valueObject[i][vk];
                    const dateTime = convertToDateTime(d, subOptionName, localization);
                    if (!dateTime) {
                        Namespace.errorMessages.typeMismatch(subOptionName, typeof d, 'DateTime or Date');
                    }
                    dateTime.setLocale(localization.locale);
                    valueObject[i][vk] = dateTime;
                });
            }
            return valueObject;
        },
        toolbarPlacement: validKeyOption(['top', 'bottom', 'default']),
        type: validKeyOption(['icons', 'sprites']),
        viewMode: validKeyOption([
            'clock',
            'calendar',
            'months',
            'years',
            'decades',
        ]),
        theme: validKeyOption(['light', 'dark', 'auto']),
        meta: ({ value }) => value,
        dayViewHeaderFormat: ({ value }) => value,
        container: ({ value, path }) => {
            if (value &&
                !(value instanceof HTMLElement ||
                    value instanceof Element ||
                    value?.appendChild)) {
                Namespace.errorMessages.typeMismatch(path.substring(1), typeof value, 'HTMLElement');
            }
            return value;
        },
        useTwentyfourHour: ({ value, path, providedType, defaultType }) => {
            Namespace.errorMessages.deprecatedWarning('useTwentyfourHour', 'Please use "options.localization.hourCycle" instead');
            if (value === undefined || providedType === 'boolean')
                return value;
            Namespace.errorMessages.typeMismatch(path, providedType, defaultType);
        },
        hourCycle: validKeyOption(['h11', 'h12', 'h23', 'h24']),
    });
    const defaultProcessor = ({ value, defaultType, providedType, path, }) => {
        switch (defaultType) {
            case 'boolean':
                return value === 'true' || value === true;
            case 'number':
                return +value;
            case 'string':
                return value.toString();
            case 'object':
                return {};
            case 'function':
                return value;
            default:
                Namespace.errorMessages.typeMismatch(path, providedType, defaultType);
        }
    };
    function processKey(args) {
        return (optionProcessors[args.key] || defaultProcessor)(args);
    }
  
    class OptionConverter {
        static deepCopy(input) {
            const o = {};
            Object.keys(input).forEach((key) => {
                const inputElement = input[key];
                if (inputElement instanceof DateTime) {
                    o[key] = inputElement.clone;
                    return;
                }
                else if (inputElement instanceof Date) {
                    o[key] = new Date(inputElement.valueOf());
                    return;
                }
                o[key] = inputElement;
                if (typeof inputElement !== 'object' ||
                    inputElement instanceof HTMLElement ||
                    inputElement instanceof Element)
                    return;
                if (!Array.isArray(inputElement)) {
                    o[key] = OptionConverter.deepCopy(inputElement);
                }
            });
            return o;
        }
        /**
         * Finds value out of an object based on a string, period delimited, path
         * @param paths
         * @param obj
         */
        static objectPath(paths, obj) {
            if (paths.charAt(0) === '.')
                paths = paths.slice(1);
            if (!paths)
                return obj;
            return paths
                .split('.')
                .reduce((value, key) => OptionConverter.isValue(value) || OptionConverter.isValue(value[key])
                ? value[key]
                : undefined, obj);
        }
        /**
         * The spread operator caused sub keys to be missing after merging.
         * This is to fix that issue by using spread on the child objects first.
         * Also handles complex options like disabledDates
         * @param provided An option from new providedOptions
         * @param copyTo Destination object. This was added to prevent reference copies
         * @param path
         * @param localization
         */
        static spread(provided, copyTo, path = '', localization) {
            const defaultOptions = OptionConverter.objectPath(path, DefaultOptions);
            const unsupportedOptions = Object.keys(provided).filter((x) => !Object.keys(defaultOptions).includes(x));
            if (unsupportedOptions.length > 0) {
                const flattenedOptions = OptionConverter.getFlattenDefaultOptions();
                const errors = unsupportedOptions.map((x) => {
                    let error = `"${path}.${x}" in not a known option.`;
                    const didYouMean = flattenedOptions.find((y) => y.includes(x));
                    if (didYouMean)
                        error += ` Did you mean "${didYouMean}"?`;
                    return error;
                });
                Namespace.errorMessages.unexpectedOptions(errors);
            }
            Object.keys(provided)
                .filter((key) => key !== '__proto__' && key !== 'constructor')
                .forEach((key) => {
                path += `.${key}`;
                if (path.charAt(0) === '.')
                    path = path.slice(1);
                const defaultOptionValue = defaultOptions[key];
                const providedType = typeof provided[key];
                const defaultType = typeof defaultOptionValue;
                const value = provided[key];
                if (value === undefined || value === null) {
                    copyTo[key] = value;
                    path = path.substring(0, path.lastIndexOf(`.${key}`));
                    return;
                }
                if (typeof defaultOptionValue === 'object' &&
                    !Array.isArray(provided[key]) &&
                    !(defaultOptionValue instanceof Date ||
                        OptionConverter.ignoreProperties.includes(key))) {
                    OptionConverter.spread(provided[key], copyTo[key], path, localization);
                }
                else {
                    copyTo[key] = OptionConverter.processKey(key, value, providedType, defaultType, path, localization);
                }
                path = path.substring(0, path.lastIndexOf(`.${key}`));
            });
        }
        static processKey(key, value, //eslint-disable-line @typescript-eslint/no-explicit-any
        providedType, defaultType, path, localization) {
            return processKey({
                key,
                value,
                providedType,
                defaultType,
                path,
                localization,
            });
        }
        static _mergeOptions(providedOptions, mergeTo) {
            const newConfig = OptionConverter.deepCopy(mergeTo);
            //see if the options specify a locale
            const localization = mergeTo.localization?.locale !== 'default'
                ? mergeTo.localization
                : providedOptions?.localization || DefaultOptions.localization;
            OptionConverter.spread(providedOptions, newConfig, '', localization);
            return newConfig;
        }
        static _dataToOptions(element, options) {
            const eData = JSON.parse(JSON.stringify(element.dataset));
            if (eData?.tdTargetInput)
                delete eData.tdTargetInput;
            if (eData?.tdTargetToggle)
                delete eData.tdTargetToggle;
            if (!eData ||
                Object.keys(eData).length === 0 ||
                eData.constructor !== DOMStringMap)
                return options;
            const dataOptions = {};
            // because dataset returns camelCase including the 'td' key the option
            // key won't align
            const objectToNormalized = (object) => {
                const lowered = {};
                Object.keys(object).forEach((x) => {
                    lowered[x.toLowerCase()] = x;
                });
                return lowered;
            };
            const rabbitHole = (split, index, optionSubgroup, value) => {
                // first round = display { ... }
                const normalizedOptions = objectToNormalized(optionSubgroup);
                const keyOption = normalizedOptions[split[index].toLowerCase()];
                const internalObject = {};
                if (keyOption === undefined)
                    return internalObject;
                // if this is another object, continue down the rabbit hole
                if (optionSubgroup[keyOption].constructor === Object) {
                    index++;
                    internalObject[keyOption] = rabbitHole(split, index, optionSubgroup[keyOption], value);
                }
                else {
                    internalObject[keyOption] = value;
                }
                return internalObject;
            };
            const optionsLower = objectToNormalized(options);
            Object.keys(eData)
                .filter((x) => x.startsWith(Namespace.dataKey))
                .map((x) => x.substring(2))
                .forEach((key) => {
                let keyOption = optionsLower[key.toLowerCase()];
                // dataset merges dashes to camelCase... yay
                // i.e. key = display_components_seconds
                if (key.includes('_')) {
                    // [display, components, seconds]
                    const split = key.split('_');
                    // display
                    keyOption = optionsLower[split[0].toLowerCase()];
                    if (keyOption !== undefined &&
                        options[keyOption].constructor === Object) {
                        dataOptions[keyOption] = rabbitHole(split, 1, options[keyOption], eData[`td${key}`]);
                    }
                }
                // or key = multipleDate
                else if (keyOption !== undefined) {
                    dataOptions[keyOption] = eData[`td${key}`];
                }
            });
            return this._mergeOptions(dataOptions, options);
        }
        /**
         * Attempts to prove `d` is a DateTime or Date or can be converted into one.
         * @param d If a string will attempt creating a date from it.
         * @param localization object containing locale and format settings. Only used with the custom formats
         * @private
         */
        static _dateTypeCheck(d, //eslint-disable-line @typescript-eslint/no-explicit-any
        localization) {
            return tryConvertToDateTime(d, localization);
        }
        /**
         * Type checks that `value` is an array of Date or DateTime
         * @param optionName Provides text to error messages e.g. disabledDates
         * @param value Option value
         * @param providedType Used to provide text to error messages
         * @param localization
         */
        static _typeCheckDateArray(optionName, value, providedType, localization) {
            return typeCheckDateArray(optionName, value, providedType, localization);
        }
        /**
         * Type checks that `value` is an array of numbers
         * @param optionName Provides text to error messages e.g. disabledDates
         * @param value Option value
         * @param providedType Used to provide text to error messages
         */
        static _typeCheckNumberArray(optionName, value, providedType) {
            return typeCheckNumberArray(optionName, value, providedType);
        }
        /**
         * Attempts to convert `d` to a DateTime object
         * @param d value to convert
         * @param optionName Provides text to error messages e.g. disabledDates
         * @param localization object containing locale and format settings. Only used with the custom formats
         */
        static dateConversion(d, //eslint-disable-line @typescript-eslint/no-explicit-any
        optionName, localization) {
            console.log(d);
            return convertToDateTime(d, optionName, localization);
        }
        static getFlattenDefaultOptions() {
            if (this._flattenDefaults)
                return this._flattenDefaults;
            const deepKeys = (t, pre = []) => {
                if (Array.isArray(t))
                    return [];
                if (Object(t) === t) {
                    return Object.entries(t).flatMap(([k, v]) => deepKeys(v, [...pre, k]));
                }
                else {
                    return pre.join('.');
                }
            };
            this._flattenDefaults = deepKeys(DefaultOptions);
            return this._flattenDefaults;
        }
        /**
         * Some options conflict like min/max date. Verify that these kinds of options
         * are set correctly.
         * @param config
         */
        static _validateConflicts(config) {
            if (config.display.sideBySide &&
                (!config.display.components.clock ||
                    !(config.display.components.hours ||
                        config.display.components.minutes ||
                        config.display.components.seconds))) {
                Namespace.errorMessages.conflictingConfiguration('Cannot use side by side mode without the clock components');
            }
            if (config.restrictions.minDate && config.restrictions.maxDate) {
                if (config.restrictions.minDate.isAfter(config.restrictions.maxDate)) {
                    Namespace.errorMessages.conflictingConfiguration('minDate is after maxDate');
                }
                if (config.restrictions.maxDate.isBefore(config.restrictions.minDate)) {
                    Namespace.errorMessages.conflictingConfiguration('maxDate is before minDate');
                }
            }
        }
    }
    OptionConverter.ignoreProperties = [
        'meta',
        'dayViewHeaderFormat',
        'container',
        'dateForms',
        'ordinal',
    ];
    OptionConverter.isValue = (a) => a != null; // everything except undefined + null
  
    class Dates {
        constructor() {
            this._dates = [];
            this.optionsStore = serviceLocator.locate(OptionsStore);
            this.validation = serviceLocator.locate(Validation);
            this._eventEmitters = serviceLocator.locate(EventEmitters);
        }
        /**
         * Returns the array of selected dates
         */
        get picked() {
            return this._dates;
        }
        /**
         * Returns the last picked value.
         */
        get lastPicked() {
            return this._dates[this.lastPickedIndex];
        }
        /**
         * Returns the length of picked dates -1 or 0 if none are selected.
         */
        get lastPickedIndex() {
            if (this._dates.length === 0)
                return 0;
            return this._dates.length - 1;
        }
        /**
         * Formats a DateTime object to a string. Used when setting the input value.
         * @param date
         */
        formatInput(date) {
            const components = this.optionsStore.options.display.components;
            if (!date)
                return '';
            return date.format({
                year: components.calendar && components.year ? 'numeric' : undefined,
                month: components.calendar && components.month ? '2-digit' : undefined,
                day: components.calendar && components.date ? '2-digit' : undefined,
                hour: components.clock && components.hours ? '2-digit' : undefined,
                minute: components.clock && components.minutes ? '2-digit' : undefined,
                second: components.clock && components.seconds ? '2-digit' : undefined,
                hourCycle: this.optionsStore.options.localization.hourCycle,
            });
        }
        /**
         * parse the value into a DateTime object.
         * this can be overwritten to supply your own parsing.
         */
        //eslint-disable-next-line @typescript-eslint/no-explicit-any
        parseInput(value) {
            //console.log(this.df.fieldname);
            console.log(frappe.datetime.user_to_str(value, false, true) + "123456789");
            let new_value = frappe.datetime.get_datetime_as_string(value);
            //let new_value = frappe.datetime.user_to_str(value, true);
            return OptionConverter.dateConversion(new_value, 'input', this.optionsStore.options.localization);
        }
        /**
         * Tries to convert the provided value to a DateTime object.
         * If value is null|undefined then clear the value of the provided index (or 0).
         * @param value Value to convert or null|undefined
         * @param index When using multidates this is the index in the array
         */
        //eslint-disable-next-line @typescript-eslint/no-explicit-any
        setFromInput(value, index) {
            if (!value) {
                this.setValue(undefined, index);
                return;
            }
            console.log(value);
            const converted = this.parseInput(value);
            if (converted) {
                converted.setLocale(this.optionsStore.options.localization.locale);
                this.setValue(converted, index);
            }
            console.log(converted);
        }
        /**
         * Adds a new DateTime to selected dates array
         * @param date
         */
        add(date) {
            this._dates.push(date);
        }
        /**
         * Returns true if the `targetDate` is part of the selected dates array.
         * If `unit` is provided then a granularity to that unit will be used.
         * @param targetDate
         * @param unit
         */
        isPicked(targetDate, unit) {
            if (!unit)
                return this._dates.find((x) => x === targetDate) !== undefined;
            const format = getFormatByUnit(unit);
            const innerDateFormatted = targetDate.format(format);
            return (this._dates
                .map((x) => x.format(format))
                .find((x) => x === innerDateFormatted) !== undefined);
        }
        /**
         * Returns the index at which `targetDate` is in the array.
         * This is used for updating or removing a date when multi-date is used
         * If `unit` is provided then a granularity to that unit will be used.
         * @param targetDate
         * @param unit
         */
        pickedIndex(targetDate, unit) {
            if (!unit)
                return this._dates.indexOf(targetDate);
            const format = getFormatByUnit(unit);
            const innerDateFormatted = targetDate.format(format);
            return this._dates.map((x) => x.format(format)).indexOf(innerDateFormatted);
        }
        /**
         * Clears all selected dates.
         */
        clear() {
            this.optionsStore.unset = true;
            this._eventEmitters.triggerEvent.emit({
                type: Namespace.events.change,
                date: undefined,
                oldDate: this.lastPicked,
                isClear: true,
                isValid: true,
            });
            this._dates = [];
        }
        /**
         * Find the "book end" years given a `year` and a `factor`
         * @param factor e.g. 100 for decades
         * @param year e.g. 2021
         */
        static getStartEndYear(factor, year) {
            const step = factor / 10, startYear = Math.floor(year / factor) * factor, endYear = startYear + step * 9, focusValue = Math.floor(year / step) * step;
            return [startYear, endYear, focusValue];
        }
        updateInput(target) {
            if (!this.optionsStore.input)
                return;
            let newValue = this.formatInput(target);
            if (this.optionsStore.options.multipleDates) {
                newValue = this._dates
                    .map((d) => this.formatInput(d))
                    .join(this.optionsStore.options.multipleDatesSeparator);
            }
            if (this.optionsStore.input.value != newValue)
                this.optionsStore.input.value = newValue;
        }
        /**
         * Attempts to either clear or set the `target` date at `index`.
         * If the `target` is null then the date will be cleared.
         * If multi-date is being used then it will be removed from the array.
         * If `target` is valid and multi-date is used then if `index` is
         * provided the date at that index will be replaced, otherwise it is appended.
         * @param target
         * @param index
         */
        setValue(target, index) {
            const noIndex = typeof index === 'undefined', isClear = !target && noIndex;
            let oldDate = this.optionsStore.unset ? null : this._dates[index];
            if (!oldDate && !this.optionsStore.unset && noIndex && isClear) {
                oldDate = this.lastPicked;
            }
            if (target && oldDate?.isSame(target)) {
                this.updateInput(target);
                return;
            }
            // case of calling setValue(null)
            if (!target) {
                if (!this.optionsStore.options.multipleDates ||
                    this._dates.length === 1 ||
                    isClear) {
                    this.optionsStore.unset = true;
                    this._dates = [];
                }
                else {
                    this._dates.splice(index, 1);
                }
                this.updateInput();
                this._eventEmitters.triggerEvent.emit({
                    type: Namespace.events.change,
                    date: undefined,
                    oldDate,
                    isClear,
                    isValid: true,
                });
                this._eventEmitters.updateDisplay.emit('all');
                return;
            }
            index = index || 0;
            target = target.clone;
            // minute stepping is being used, force the minute to the closest value
            if (this.optionsStore.options.stepping !== 1) {
                target.minutes =
                    Math.round(target.minutes / this.optionsStore.options.stepping) *
                        this.optionsStore.options.stepping;
                target.seconds = 0;
            }
            if (this.validation.isValid(target)) {
                this._dates[index] = target;
                this._eventEmitters.updateViewDate.emit(target.clone);
                this.updateInput(target);
                this.optionsStore.unset = false;
                this._eventEmitters.updateDisplay.emit('all');
                this._eventEmitters.triggerEvent.emit({
                    type: Namespace.events.change,
                    date: target,
                    oldDate,
                    isClear,
                    isValid: true,
                });
                return;
            }
            if (this.optionsStore.options.keepInvalid) {
                this._dates[index] = target;
                this._eventEmitters.updateViewDate.emit(target.clone);
                this.updateInput(target);
                this._eventEmitters.triggerEvent.emit({
                    type: Namespace.events.change,
                    date: target,
                    oldDate,
                    isClear,
                    isValid: false,
                });
            }
            this._eventEmitters.triggerEvent.emit({
                type: Namespace.events.error,
                reason: Namespace.errorMessages.failedToSetInvalidDate,
                date: target,
                oldDate,
            });
        }
    }
  
    var ActionTypes;
    (function (ActionTypes) {
        ActionTypes["next"] = "next";
        ActionTypes["previous"] = "previous";
        ActionTypes["changeCalendarView"] = "changeCalendarView";
        ActionTypes["selectMonth"] = "selectMonth";
        ActionTypes["selectYear"] = "selectYear";
        ActionTypes["selectDecade"] = "selectDecade";
        ActionTypes["selectDay"] = "selectDay";
        ActionTypes["selectHour"] = "selectHour";
        ActionTypes["selectMinute"] = "selectMinute";
        ActionTypes["selectSecond"] = "selectSecond";
        ActionTypes["incrementHours"] = "incrementHours";
        ActionTypes["incrementMinutes"] = "incrementMinutes";
        ActionTypes["incrementSeconds"] = "incrementSeconds";
        ActionTypes["decrementHours"] = "decrementHours";
        ActionTypes["decrementMinutes"] = "decrementMinutes";
        ActionTypes["decrementSeconds"] = "decrementSeconds";
        ActionTypes["toggleMeridiem"] = "toggleMeridiem";
        ActionTypes["togglePicker"] = "togglePicker";
        ActionTypes["showClock"] = "showClock";
        ActionTypes["showHours"] = "showHours";
        ActionTypes["showMinutes"] = "showMinutes";
        ActionTypes["showSeconds"] = "showSeconds";
        ActionTypes["clear"] = "clear";
        ActionTypes["close"] = "close";
        ActionTypes["today"] = "today";
    })(ActionTypes || (ActionTypes = {}));
    var ActionTypes$1 = ActionTypes;
  
    /**
     * Creates and updates the grid for `date`
     */
    class DateDisplay {
        constructor() {
            this.optionsStore = serviceLocator.locate(OptionsStore);
            this.dates = serviceLocator.locate(Dates);
            this.validation = serviceLocator.locate(Validation);
        }
        /**
         * Build the container html for the display
         * @private
         */
        getPicker() {
            const container = document.createElement('div');
            container.classList.add(Namespace.css.daysContainer);
            container.append(...this._daysOfTheWeek());
            if (this.optionsStore.options.display.calendarWeeks) {
                const div = document.createElement('div');
                div.classList.add(Namespace.css.calendarWeeks, Namespace.css.noHighlight);
                container.appendChild(div);
            }
            for (let i = 0; i < 42; i++) {
                if (i !== 0 && i % 7 === 0) {
                    if (this.optionsStore.options.display.calendarWeeks) {
                        const div = document.createElement('div');
                        div.classList.add(Namespace.css.calendarWeeks, Namespace.css.noHighlight);
                        container.appendChild(div);
                    }
                }
                const div = document.createElement('div');
                div.setAttribute('data-action', ActionTypes$1.selectDay);
                container.appendChild(div);
            }
            return container;
        }
        /**
         * Populates the grid and updates enabled states
         * @private
         */
        _update(widget, paint) {
            const container = widget.getElementsByClassName(Namespace.css.daysContainer)[0];
            if (this.optionsStore.currentView === 'calendar') {
                const [previous, switcher, next] = container.parentElement
                    .getElementsByClassName(Namespace.css.calendarHeader)[0]
                    .getElementsByTagName('div');
                switcher.setAttribute(Namespace.css.daysContainer, this.optionsStore.viewDate.format(this.optionsStore.options.localization.dayViewHeaderFormat));
                this.optionsStore.options.display.components.month
                    ? switcher.classList.remove(Namespace.css.disabled)
                    : switcher.classList.add(Namespace.css.disabled);
                this.validation.isValid(this.optionsStore.viewDate.clone.manipulate(-1, exports.Unit.month), exports.Unit.month)
                    ? previous.classList.remove(Namespace.css.disabled)
                    : previous.classList.add(Namespace.css.disabled);
                this.validation.isValid(this.optionsStore.viewDate.clone.manipulate(1, exports.Unit.month), exports.Unit.month)
                    ? next.classList.remove(Namespace.css.disabled)
                    : next.classList.add(Namespace.css.disabled);
            }
            const innerDate = this.optionsStore.viewDate.clone
                .startOf(exports.Unit.month)
                .startOf('weekDay', this.optionsStore.options.localization.startOfTheWeek)
                .manipulate(12, exports.Unit.hours);
            container
                .querySelectorAll(`[data-action="${ActionTypes$1.selectDay}"], .${Namespace.css.calendarWeeks}`)
                .forEach((containerClone) => {
                if (this.optionsStore.options.display.calendarWeeks &&
                    containerClone.classList.contains(Namespace.css.calendarWeeks)) {
                    if (containerClone.innerText === '#')
                        return;
                    containerClone.innerText = `${innerDate.week}`;
                    return;
                }
                const classes = [];
                classes.push(Namespace.css.day);
                if (innerDate.isBefore(this.optionsStore.viewDate, exports.Unit.month)) {
                    classes.push(Namespace.css.old);
                }
                if (innerDate.isAfter(this.optionsStore.viewDate, exports.Unit.month)) {
                    classes.push(Namespace.css.new);
                }
                if (!this.optionsStore.unset &&
                    this.dates.isPicked(innerDate, exports.Unit.date)) {
                    classes.push(Namespace.css.active);
                    classes.push(Namespace.css.btn);
                }
                if (!this.validation.isValid(innerDate, exports.Unit.date)) {
                    classes.push(Namespace.css.disabled);
                }
                if (innerDate.isSame(new DateTime(), exports.Unit.date)) {
                    classes.push(Namespace.css.today);
                }
                if (innerDate.weekDay === 0 || innerDate.weekDay === 6) {
                    classes.push(Namespace.css.weekend);
                }
                paint(exports.Unit.date, innerDate, classes, containerClone);
                containerClone.classList.remove(...containerClone.classList);
                containerClone.classList.add(...classes);
                containerClone.setAttribute('data-value', `${innerDate.year}-${innerDate.monthFormatted}-${innerDate.dateFormatted}`);
                containerClone.setAttribute('data-day', `${innerDate.date}`);
                containerClone.innerText = innerDate.format({ day: 'numeric' });
                innerDate.manipulate(1, exports.Unit.date);
            });
        }
        /***
         * Generates an html row that contains the days of the week.
         * @private
         */
        _daysOfTheWeek() {
            const innerDate = this.optionsStore.viewDate.clone
                .startOf('weekDay', this.optionsStore.options.localization.startOfTheWeek)
                .startOf(exports.Unit.date);
            const row = [];
            document.createElement('div');
            if (this.optionsStore.options.display.calendarWeeks) {
                const htmlDivElement = document.createElement('div');
                htmlDivElement.classList.add(Namespace.css.calendarWeeks, Namespace.css.noHighlight);
                htmlDivElement.innerText = '#';
                row.push(htmlDivElement);
            }
            for (let i = 0; i < 7; i++) {
                const htmlDivElement = document.createElement('div');
                htmlDivElement.classList.add(Namespace.css.dayOfTheWeek, Namespace.css.noHighlight);
                htmlDivElement.innerText = innerDate.format({ weekday: 'short' });
                innerDate.manipulate(1, exports.Unit.date);
                row.push(htmlDivElement);
            }
            return row;
        }
    }
  
    /**
     * Creates and updates the grid for `month`
     */
    class MonthDisplay {
        constructor() {
            this.optionsStore = serviceLocator.locate(OptionsStore);
            this.dates = serviceLocator.locate(Dates);
            this.validation = serviceLocator.locate(Validation);
        }
        /**
         * Build the container html for the display
         * @private
         */
        getPicker() {
            const container = document.createElement('div');
            container.classList.add(Namespace.css.monthsContainer);
            for (let i = 0; i < 12; i++) {
                const div = document.createElement('div');
                div.setAttribute('data-action', ActionTypes$1.selectMonth);
                container.appendChild(div);
            }
            return container;
        }
        /**
         * Populates the grid and updates enabled states
         * @private
         */
        _update(widget, paint) {
            const container = widget.getElementsByClassName(Namespace.css.monthsContainer)[0];
            if (this.optionsStore.currentView === 'months') {
                const [previous, switcher, next] = container.parentElement
                    .getElementsByClassName(Namespace.css.calendarHeader)[0]
                    .getElementsByTagName('div');
                switcher.setAttribute(Namespace.css.monthsContainer, this.optionsStore.viewDate.format({ year: 'numeric' }));
                this.optionsStore.options.display.components.year
                    ? switcher.classList.remove(Namespace.css.disabled)
                    : switcher.classList.add(Namespace.css.disabled);
                this.validation.isValid(this.optionsStore.viewDate.clone.manipulate(-1, exports.Unit.year), exports.Unit.year)
                    ? previous.classList.remove(Namespace.css.disabled)
                    : previous.classList.add(Namespace.css.disabled);
                this.validation.isValid(this.optionsStore.viewDate.clone.manipulate(1, exports.Unit.year), exports.Unit.year)
                    ? next.classList.remove(Namespace.css.disabled)
                    : next.classList.add(Namespace.css.disabled);
            }
            const innerDate = this.optionsStore.viewDate.clone.startOf(exports.Unit.year);
            container
                .querySelectorAll(`[data-action="${ActionTypes$1.selectMonth}"]`)
                .forEach((containerClone, index) => {
                const classes = [];
                classes.push(Namespace.css.month);
                if (!this.optionsStore.unset &&
                    this.dates.isPicked(innerDate, exports.Unit.month)) {
                    classes.push(Namespace.css.active);
                    classes.push(Namespace.css.btn);
                }
                if (!this.validation.isValid(innerDate, exports.Unit.month)) {
                    classes.push(Namespace.css.disabled);
                }
                paint(exports.Unit.month, innerDate, classes, containerClone);
                containerClone.classList.remove(...containerClone.classList);
                containerClone.classList.add(...classes);
                containerClone.setAttribute('data-value', `${index}`);
                containerClone.innerText = `${innerDate.format({ month: 'short' })}`;
                innerDate.manipulate(1, exports.Unit.month);
            });
        }
    }
  
    /**
     * Creates and updates the grid for `year`
     */
    class YearDisplay {
        constructor() {
            this.optionsStore = serviceLocator.locate(OptionsStore);
            this.dates = serviceLocator.locate(Dates);
            this.validation = serviceLocator.locate(Validation);
        }
        /**
         * Build the container html for the display
         * @private
         */
        getPicker() {
            const container = document.createElement('div');
            container.classList.add(Namespace.css.yearsContainer);
            for (let i = 0; i < 12; i++) {
                const div = document.createElement('div');
                div.setAttribute('data-action', ActionTypes$1.selectYear);
                container.appendChild(div);
            }
            return container;
        }
        /**
         * Populates the grid and updates enabled states
         * @private
         */
        _update(widget, paint) {
            this._startYear = this.optionsStore.viewDate.clone.manipulate(-1, exports.Unit.year);
            this._endYear = this.optionsStore.viewDate.clone.manipulate(10, exports.Unit.year);
            const container = widget.getElementsByClassName(Namespace.css.yearsContainer)[0];
            if (this.optionsStore.currentView === 'years') {
                const [previous, switcher, next] = container.parentElement
                    .getElementsByClassName(Namespace.css.calendarHeader)[0]
                    .getElementsByTagName('div');
                switcher.setAttribute(Namespace.css.yearsContainer, `${this._startYear.format({ year: 'numeric' })}-${this._endYear.format({
                  year: 'numeric',
              })}`);
                this.optionsStore.options.display.components.decades
                    ? switcher.classList.remove(Namespace.css.disabled)
                    : switcher.classList.add(Namespace.css.disabled);
                this.validation.isValid(this._startYear, exports.Unit.year)
                    ? previous.classList.remove(Namespace.css.disabled)
                    : previous.classList.add(Namespace.css.disabled);
                this.validation.isValid(this._endYear, exports.Unit.year)
                    ? next.classList.remove(Namespace.css.disabled)
                    : next.classList.add(Namespace.css.disabled);
            }
            const innerDate = this.optionsStore.viewDate.clone
                .startOf(exports.Unit.year)
                .manipulate(-1, exports.Unit.year);
            container
                .querySelectorAll(`[data-action="${ActionTypes$1.selectYear}"]`)
                .forEach((containerClone) => {
                const classes = [];
                classes.push(Namespace.css.year);
                if (!this.optionsStore.unset &&
                    this.dates.isPicked(innerDate, exports.Unit.year)) {
                    classes.push(Namespace.css.active);
                    classes.push(Namespace.css.btn);
                }
                if (!this.validation.isValid(innerDate, exports.Unit.year)) {
                    classes.push(Namespace.css.disabled);
                }
                paint(exports.Unit.year, innerDate, classes, containerClone);
                containerClone.classList.remove(...containerClone.classList);
                containerClone.classList.add(...classes);
                containerClone.setAttribute('data-value', `${innerDate.year}`);
                containerClone.innerText = innerDate.format({ year: 'numeric' });
                innerDate.manipulate(1, exports.Unit.year);
            });
        }
    }
  
    /**
     * Creates and updates the grid for `seconds`
     */
    class DecadeDisplay {
        constructor() {
            this.optionsStore = serviceLocator.locate(OptionsStore);
            this.dates = serviceLocator.locate(Dates);
            this.validation = serviceLocator.locate(Validation);
        }
        /**
         * Build the container html for the display
         * @private
         */
        getPicker() {
            const container = document.createElement('div');
            container.classList.add(Namespace.css.decadesContainer);
            for (let i = 0; i < 12; i++) {
                const div = document.createElement('div');
                div.setAttribute('data-action', ActionTypes$1.selectDecade);
                container.appendChild(div);
            }
            return container;
        }
        /**
         * Populates the grid and updates enabled states
         * @private
         */
        _update(widget, paint) {
            const [start, end] = Dates.getStartEndYear(100, this.optionsStore.viewDate.year);
            this._startDecade = this.optionsStore.viewDate.clone.startOf(exports.Unit.year);
            this._startDecade.year = start;
            this._endDecade = this.optionsStore.viewDate.clone.startOf(exports.Unit.year);
            this._endDecade.year = end;
            const container = widget.getElementsByClassName(Namespace.css.decadesContainer)[0];
            const [previous, switcher, next] = container.parentElement
                .getElementsByClassName(Namespace.css.calendarHeader)[0]
                .getElementsByTagName('div');
            if (this.optionsStore.currentView === 'decades') {
                switcher.setAttribute(Namespace.css.decadesContainer, `${this._startDecade.format({
                  year: 'numeric',
              })}-${this._endDecade.format({ year: 'numeric' })}`);
                this.validation.isValid(this._startDecade, exports.Unit.year)
                    ? previous.classList.remove(Namespace.css.disabled)
                    : previous.classList.add(Namespace.css.disabled);
                this.validation.isValid(this._endDecade, exports.Unit.year)
                    ? next.classList.remove(Namespace.css.disabled)
                    : next.classList.add(Namespace.css.disabled);
            }
            const pickedYears = this.dates.picked.map((x) => x.year);
            container
                .querySelectorAll(`[data-action="${ActionTypes$1.selectDecade}"]`)
                .forEach((containerClone, index) => {
                if (index === 0) {
                    containerClone.classList.add(Namespace.css.old);
                    if (this._startDecade.year - 10 < 0) {
                        containerClone.textContent = ' ';
                        previous.classList.add(Namespace.css.disabled);
                        containerClone.classList.add(Namespace.css.disabled);
                        containerClone.setAttribute('data-value', '');
                        return;
                    }
                    else {
                        containerClone.innerText = this._startDecade.clone
                            .manipulate(-10, exports.Unit.year)
                            .format({ year: 'numeric' });
                        containerClone.setAttribute('data-value', `${this._startDecade.year}`);
                        return;
                    }
                }
                const classes = [];
                classes.push(Namespace.css.decade);
                const startDecadeYear = this._startDecade.year;
                const endDecadeYear = this._startDecade.year + 9;
                if (!this.optionsStore.unset &&
                    pickedYears.filter((x) => x >= startDecadeYear && x <= endDecadeYear)
                        .length > 0) {
                    classes.push(Namespace.css.active);
                    classes.push(Namespace.css.btn);
                }
                paint('decade', this._startDecade, classes, containerClone);
                containerClone.classList.remove(...containerClone.classList);
                containerClone.classList.add(...classes);
                containerClone.setAttribute('data-value', `${this._startDecade.year}`);
                containerClone.innerText = `${this._startDecade.format({
                  year: 'numeric',
              })}`;
                this._startDecade.manipulate(10, exports.Unit.year);
            });
        }
    }
  
    /**
     * Creates the clock display
     */
    class TimeDisplay {
        constructor() {
            this._gridColumns = '';
            this.optionsStore = serviceLocator.locate(OptionsStore);
            this.dates = serviceLocator.locate(Dates);
            this.validation = serviceLocator.locate(Validation);
        }
        /**
         * Build the container html for the clock display
         * @private
         */
        getPicker(iconTag) {
            const container = document.createElement('div');
            container.classList.add(Namespace.css.clockContainer);
            container.append(...this._grid(iconTag));
            return container;
        }
        /**
         * Populates the various elements with in the clock display
         * like the current hour and if the manipulation icons are enabled.
         * @private
         */
        _update(widget) {
            const timesDiv = (widget.getElementsByClassName(Namespace.css.clockContainer)[0]);
            const lastPicked = (this.dates.lastPicked || this.optionsStore.viewDate)
                .clone;
            timesDiv
                .querySelectorAll('.disabled')
                .forEach((element) => element.classList.remove(Namespace.css.disabled));
            if (this.optionsStore.options.display.components.hours) {
                if (!this.validation.isValid(this.optionsStore.viewDate.clone.manipulate(1, exports.Unit.hours), exports.Unit.hours)) {
                    timesDiv
                        .querySelector(`[data-action=${ActionTypes$1.incrementHours}]`)
                        .classList.add(Namespace.css.disabled);
                }
                if (!this.validation.isValid(this.optionsStore.viewDate.clone.manipulate(-1, exports.Unit.hours), exports.Unit.hours)) {
                    timesDiv
                        .querySelector(`[data-action=${ActionTypes$1.decrementHours}]`)
                        .classList.add(Namespace.css.disabled);
                }
                timesDiv.querySelector(`[data-time-component=${exports.Unit.hours}]`).innerText = lastPicked.getHoursFormatted(this.optionsStore.options.localization.hourCycle);
            }
            if (this.optionsStore.options.display.components.minutes) {
                if (!this.validation.isValid(this.optionsStore.viewDate.clone.manipulate(1, exports.Unit.minutes), exports.Unit.minutes)) {
                    timesDiv
                        .querySelector(`[data-action=${ActionTypes$1.incrementMinutes}]`)
                        .classList.add(Namespace.css.disabled);
                }
                if (!this.validation.isValid(this.optionsStore.viewDate.clone.manipulate(-1, exports.Unit.minutes), exports.Unit.minutes)) {
                    timesDiv
                        .querySelector(`[data-action=${ActionTypes$1.decrementMinutes}]`)
                        .classList.add(Namespace.css.disabled);
                }
                timesDiv.querySelector(`[data-time-component=${exports.Unit.minutes}]`).innerText = lastPicked.minutesFormatted;
            }
            if (this.optionsStore.options.display.components.seconds) {
                if (!this.validation.isValid(this.optionsStore.viewDate.clone.manipulate(1, exports.Unit.seconds), exports.Unit.seconds)) {
                    timesDiv
                        .querySelector(`[data-action=${ActionTypes$1.incrementSeconds}]`)
                        .classList.add(Namespace.css.disabled);
                }
                if (!this.validation.isValid(this.optionsStore.viewDate.clone.manipulate(-1, exports.Unit.seconds), exports.Unit.seconds)) {
                    timesDiv
                        .querySelector(`[data-action=${ActionTypes$1.decrementSeconds}]`)
                        .classList.add(Namespace.css.disabled);
                }
                timesDiv.querySelector(`[data-time-component=${exports.Unit.seconds}]`).innerText = lastPicked.secondsFormatted;
            }
            if (this.optionsStore.isTwelveHour) {
                const toggle = timesDiv.querySelector(`[data-action=${ActionTypes$1.toggleMeridiem}]`);
                toggle.innerText = lastPicked.meridiem();
                if (!this.validation.isValid(lastPicked.clone.manipulate(lastPicked.hours >= 12 ? -12 : 12, exports.Unit.hours))) {
                    toggle.classList.add(Namespace.css.disabled);
                }
                else {
                    toggle.classList.remove(Namespace.css.disabled);
                }
            }
            timesDiv.style.gridTemplateAreas = `"${this._gridColumns}"`;
        }
        /**
         * Creates the table for the clock display depending on what options are selected.
         * @private
         */
        _grid(iconTag) {
            this._gridColumns = '';
            const top = [], middle = [], bottom = [], separator = document.createElement('div'), upIcon = iconTag(this.optionsStore.options.display.icons.up), downIcon = iconTag(this.optionsStore.options.display.icons.down);
            separator.classList.add(Namespace.css.separator, Namespace.css.noHighlight);
            const separatorColon = separator.cloneNode(true);
            separatorColon.innerHTML = ':';
            const getSeparator = (colon = false) => {
                return colon
                    ? separatorColon.cloneNode(true)
                    : separator.cloneNode(true);
            };
            if (this.optionsStore.options.display.components.hours) {
                let divElement = document.createElement('div');
                divElement.setAttribute('title', this.optionsStore.options.localization.incrementHour);
                divElement.setAttribute('data-action', ActionTypes$1.incrementHours);
                divElement.appendChild(upIcon.cloneNode(true));
                top.push(divElement);
                divElement = document.createElement('div');
                divElement.setAttribute('title', this.optionsStore.options.localization.pickHour);
                divElement.setAttribute('data-action', ActionTypes$1.showHours);
                divElement.setAttribute('data-time-component', exports.Unit.hours);
                middle.push(divElement);
                divElement = document.createElement('div');
                divElement.setAttribute('title', this.optionsStore.options.localization.decrementHour);
                divElement.setAttribute('data-action', ActionTypes$1.decrementHours);
                divElement.appendChild(downIcon.cloneNode(true));
                bottom.push(divElement);
                this._gridColumns += 'a';
            }
            if (this.optionsStore.options.display.components.minutes) {
                this._gridColumns += ' a';
                if (this.optionsStore.options.display.components.hours) {
                    top.push(getSeparator());
                    middle.push(getSeparator(true));
                    bottom.push(getSeparator());
                    this._gridColumns += ' a';
                }
                let divElement = document.createElement('div');
                divElement.setAttribute('title', this.optionsStore.options.localization.incrementMinute);
                divElement.setAttribute('data-action', ActionTypes$1.incrementMinutes);
                divElement.appendChild(upIcon.cloneNode(true));
                top.push(divElement);
                divElement = document.createElement('div');
                divElement.setAttribute('title', this.optionsStore.options.localization.pickMinute);
                divElement.setAttribute('data-action', ActionTypes$1.showMinutes);
                divElement.setAttribute('data-time-component', exports.Unit.minutes);
                middle.push(divElement);
                divElement = document.createElement('div');
                divElement.setAttribute('title', this.optionsStore.options.localization.decrementMinute);
                divElement.setAttribute('data-action', ActionTypes$1.decrementMinutes);
                divElement.appendChild(downIcon.cloneNode(true));
                bottom.push(divElement);
            }
            if (this.optionsStore.options.display.components.seconds) {
                this._gridColumns += ' a';
                if (this.optionsStore.options.display.components.minutes) {
                    top.push(getSeparator());
                    middle.push(getSeparator(true));
                    bottom.push(getSeparator());
                    this._gridColumns += ' a';
                }
                let divElement = document.createElement('div');
                divElement.setAttribute('title', this.optionsStore.options.localization.incrementSecond);
                divElement.setAttribute('data-action', ActionTypes$1.incrementSeconds);
                divElement.appendChild(upIcon.cloneNode(true));
                top.push(divElement);
                divElement = document.createElement('div');
                divElement.setAttribute('title', this.optionsStore.options.localization.pickSecond);
                divElement.setAttribute('data-action', ActionTypes$1.showSeconds);
                divElement.setAttribute('data-time-component', exports.Unit.seconds);
                middle.push(divElement);
                divElement = document.createElement('div');
                divElement.setAttribute('title', this.optionsStore.options.localization.decrementSecond);
                divElement.setAttribute('data-action', ActionTypes$1.decrementSeconds);
                divElement.appendChild(downIcon.cloneNode(true));
                bottom.push(divElement);
            }
            if (this.optionsStore.isTwelveHour) {
                this._gridColumns += ' a';
                let divElement = getSeparator();
                top.push(divElement);
                const button = document.createElement('button');
                button.setAttribute('title', this.optionsStore.options.localization.toggleMeridiem);
                button.setAttribute('data-action', ActionTypes$1.toggleMeridiem);
                button.setAttribute('tabindex', '-1');
                if (Namespace.css.toggleMeridiem.includes(',')) {
                    //todo move this to paint function?
                    button.classList.add(...Namespace.css.toggleMeridiem.split(','));
                }
                else
                    button.classList.add(Namespace.css.toggleMeridiem);
                divElement = document.createElement('div');
                divElement.classList.add(Namespace.css.noHighlight);
                divElement.appendChild(button);
                middle.push(divElement);
                divElement = getSeparator();
                bottom.push(divElement);
            }
            this._gridColumns = this._gridColumns.trim();
            return [...top, ...middle, ...bottom];
        }
    }
  
    /**
     * Creates and updates the grid for `hours`
     */
    class HourDisplay {
        constructor() {
            this.optionsStore = serviceLocator.locate(OptionsStore);
            this.validation = serviceLocator.locate(Validation);
        }
        /**
         * Build the container html for the display
         * @private
         */
        getPicker() {
            const container = document.createElement('div');
            container.classList.add(Namespace.css.hourContainer);
            for (let i = 0; i < (this.optionsStore.isTwelveHour ? 12 : 24); i++) {
                const div = document.createElement('div');
                div.setAttribute('data-action', ActionTypes$1.selectHour);
                container.appendChild(div);
            }
            return container;
        }
        /**
         * Populates the grid and updates enabled states
         * @private
         */
        _update(widget, paint) {
            const container = widget.getElementsByClassName(Namespace.css.hourContainer)[0];
            const innerDate = this.optionsStore.viewDate.clone.startOf(exports.Unit.date);
            container
                .querySelectorAll(`[data-action="${ActionTypes$1.selectHour}"]`)
                .forEach((containerClone) => {
                const classes = [];
                classes.push(Namespace.css.hour);
                if (!this.validation.isValid(innerDate, exports.Unit.hours)) {
                    classes.push(Namespace.css.disabled);
                }
                paint(exports.Unit.hours, innerDate, classes, containerClone);
                containerClone.classList.remove(...containerClone.classList);
                containerClone.classList.add(...classes);
                containerClone.setAttribute('data-value', `${innerDate.hours}`);
                containerClone.innerText = innerDate.getHoursFormatted(this.optionsStore.options.localization.hourCycle);
                innerDate.manipulate(1, exports.Unit.hours);
            });
        }
    }
  
    /**
     * Creates and updates the grid for `minutes`
     */
    class MinuteDisplay {
        constructor() {
            this.optionsStore = serviceLocator.locate(OptionsStore);
            this.validation = serviceLocator.locate(Validation);
        }
        /**
         * Build the container html for the display
         * @private
         */
        getPicker() {
            const container = document.createElement('div');
            container.classList.add(Namespace.css.minuteContainer);
            const step = this.optionsStore.options.stepping === 1
                ? 5
                : this.optionsStore.options.stepping;
            for (let i = 0; i < 60 / step; i++) {
                const div = document.createElement('div');
                div.setAttribute('data-action', ActionTypes$1.selectMinute);
                container.appendChild(div);
            }
            return container;
        }
        /**
         * Populates the grid and updates enabled states
         * @private
         */
        _update(widget, paint) {
            const container = widget.getElementsByClassName(Namespace.css.minuteContainer)[0];
            const innerDate = this.optionsStore.viewDate.clone.startOf(exports.Unit.hours);
            const step = this.optionsStore.options.stepping === 1
                ? 5
                : this.optionsStore.options.stepping;
            container
                .querySelectorAll(`[data-action="${ActionTypes$1.selectMinute}"]`)
                .forEach((containerClone) => {
                const classes = [];
                classes.push(Namespace.css.minute);
                if (!this.validation.isValid(innerDate, exports.Unit.minutes)) {
                    classes.push(Namespace.css.disabled);
                }
                paint(exports.Unit.minutes, innerDate, classes, containerClone);
                containerClone.classList.remove(...containerClone.classList);
                containerClone.classList.add(...classes);
                containerClone.setAttribute('data-value', `${innerDate.minutes}`);
                containerClone.innerText = innerDate.minutesFormatted;
                innerDate.manipulate(step, exports.Unit.minutes);
            });
        }
    }
  
    /**
     * Creates and updates the grid for `seconds`
     */
    class secondDisplay {
        constructor() {
            this.optionsStore = serviceLocator.locate(OptionsStore);
            this.validation = serviceLocator.locate(Validation);
        }
        /**
         * Build the container html for the display
         * @private
         */
        getPicker() {
            const container = document.createElement('div');
            container.classList.add(Namespace.css.secondContainer);
            for (let i = 0; i < 12; i++) {
                const div = document.createElement('div');
                div.setAttribute('data-action', ActionTypes$1.selectSecond);
                container.appendChild(div);
            }
            return container;
        }
        /**
         * Populates the grid and updates enabled states
         * @private
         */
        _update(widget, paint) {
            const container = widget.getElementsByClassName(Namespace.css.secondContainer)[0];
            const innerDate = this.optionsStore.viewDate.clone.startOf(exports.Unit.minutes);
            container
                .querySelectorAll(`[data-action="${ActionTypes$1.selectSecond}"]`)
                .forEach((containerClone) => {
                const classes = [];
                classes.push(Namespace.css.second);
                if (!this.validation.isValid(innerDate, exports.Unit.seconds)) {
                    classes.push(Namespace.css.disabled);
                }
                paint(exports.Unit.seconds, innerDate, classes, containerClone);
                containerClone.classList.remove(...containerClone.classList);
                containerClone.classList.add(...classes);
                containerClone.setAttribute('data-value', `${innerDate.seconds}`);
                containerClone.innerText = innerDate.secondsFormatted;
                innerDate.manipulate(5, exports.Unit.seconds);
            });
        }
    }
  
    /**
     * Provides a collapse functionality to the view changes
     */
    class Collapse {
        /**
         * Flips the show/hide state of `target`
         * @param target html element to affect.
         */
        static toggle(target) {
            if (target.classList.contains(Namespace.css.show)) {
                this.hide(target);
            }
            else {
                this.show(target);
            }
        }
        /**
         * Skips any animation or timeouts and immediately set the element to show.
         * @param target
         */
        static showImmediately(target) {
            target.classList.remove(Namespace.css.collapsing);
            target.classList.add(Namespace.css.collapse, Namespace.css.show);
            target.style.height = '';
        }
        /**
         * If `target` is not already showing, then show after the animation.
         * @param target
         */
        static show(target) {
            if (target.classList.contains(Namespace.css.collapsing) ||
                target.classList.contains(Namespace.css.show))
                return;
            const complete = () => {
                Collapse.showImmediately(target);
            };
            target.style.height = '0';
            target.classList.remove(Namespace.css.collapse);
            target.classList.add(Namespace.css.collapsing);
            //eslint-disable-next-line @typescript-eslint/no-unused-vars
            setTimeout(complete, this.getTransitionDurationFromElement(target));
            target.style.height = `${target.scrollHeight}px`;
        }
        /**
         * Skips any animation or timeouts and immediately set the element to hide.
         * @param target
         */
        static hideImmediately(target) {
            if (!target)
                return;
            target.classList.remove(Namespace.css.collapsing, Namespace.css.show);
            target.classList.add(Namespace.css.collapse);
        }
        /**
         * If `target` is not already hidden, then hide after the animation.
         * @param target HTML Element
         */
        static hide(target) {
            if (target.classList.contains(Namespace.css.collapsing) ||
                !target.classList.contains(Namespace.css.show))
                return;
            const complete = () => {
                Collapse.hideImmediately(target);
            };
            target.style.height = `${target.getBoundingClientRect()['height']}px`;
            const reflow = (element) => element.offsetHeight;
            reflow(target);
            target.classList.remove(Namespace.css.collapse, Namespace.css.show);
            target.classList.add(Namespace.css.collapsing);
            target.style.height = '';
            //eslint-disable-next-line @typescript-eslint/no-unused-vars
            setTimeout(complete, this.getTransitionDurationFromElement(target));
        }
    }
    /**
     * Gets the transition duration from the `element` by getting css properties
     * `transition-duration` and `transition-delay`
     * @param element HTML Element
     */
    Collapse.getTransitionDurationFromElement = (element) => {
        if (!element) {
            return 0;
        }
        // Get transition-duration of the element
        let { transitionDuration, transitionDelay } = window.getComputedStyle(element);
        const floatTransitionDuration = Number.parseFloat(transitionDuration);
        const floatTransitionDelay = Number.parseFloat(transitionDelay);
        // Return 0 if element or transition duration is not found
        if (!floatTransitionDuration && !floatTransitionDelay) {
            return 0;
        }
        // If multiple durations are defined, take the first
        transitionDuration = transitionDuration.split(',')[0];
        transitionDelay = transitionDelay.split(',')[0];
        return ((Number.parseFloat(transitionDuration) +
            Number.parseFloat(transitionDelay)) *
            1000);
    };
  
    /**
     * Main class for all things display related.
     */
    class Display {
        constructor() {
            this._isVisible = false;
            /**
             * A document click event to hide the widget if click is outside
             * @private
             * @param e MouseEvent
             */
            this._documentClickEvent = (e) => {
                if (this.optionsStore.options.debug || window.debug)
                    return; //eslint-disable-line @typescript-eslint/no-explicit-any
                if (this._isVisible &&
                    !e.composedPath().includes(this.widget) && // click inside the widget
                    !e.composedPath()?.includes(this.optionsStore.element) // click on the element
                ) {
                    this.hide();
                }
            };
            /**
             * Click event for any action like selecting a date
             * @param e MouseEvent
             * @private
             */
            this._actionsClickEvent = (e) => {
                this._eventEmitters.action.emit({ e: e });
            };
            this.optionsStore = serviceLocator.locate(OptionsStore);
            this.validation = serviceLocator.locate(Validation);
            this.dates = serviceLocator.locate(Dates);
            this.dateDisplay = serviceLocator.locate(DateDisplay);
            this.monthDisplay = serviceLocator.locate(MonthDisplay);
            this.yearDisplay = serviceLocator.locate(YearDisplay);
            this.decadeDisplay = serviceLocator.locate(DecadeDisplay);
            this.timeDisplay = serviceLocator.locate(TimeDisplay);
            this.hourDisplay = serviceLocator.locate(HourDisplay);
            this.minuteDisplay = serviceLocator.locate(MinuteDisplay);
            this.secondDisplay = serviceLocator.locate(secondDisplay);
            this._eventEmitters = serviceLocator.locate(EventEmitters);
            this._widget = undefined;
            this._eventEmitters.updateDisplay.subscribe((result) => {
                this._update(result);
            });
        }
        /**
         * Returns the widget body or undefined
         * @private
         */
        get widget() {
            return this._widget;
        }
        /**
         * Returns this visible state of the picker (shown)
         */
        get isVisible() {
            return this._isVisible;
        }
        /**
         * Updates the table for a particular unit. Used when an option as changed or
         * whenever the class list might need to be refreshed.
         * @param unit
         * @private
         */
        _update(unit) {
            if (!this.widget)
                return;
            //todo do I want some kind of error catching or other guards here?
            switch (unit) {
                case exports.Unit.seconds:
                    this.secondDisplay._update(this.widget, this.paint);
                    break;
                case exports.Unit.minutes:
                    this.minuteDisplay._update(this.widget, this.paint);
                    break;
                case exports.Unit.hours:
                    this.hourDisplay._update(this.widget, this.paint);
                    break;
                case exports.Unit.date:
                    this.dateDisplay._update(this.widget, this.paint);
                    break;
                case exports.Unit.month:
                    this.monthDisplay._update(this.widget, this.paint);
                    break;
                case exports.Unit.year:
                    this.yearDisplay._update(this.widget, this.paint);
                    break;
                case 'clock':
                    if (!this._hasTime)
                        break;
                    this.timeDisplay._update(this.widget);
                    this._update(exports.Unit.hours);
                    this._update(exports.Unit.minutes);
                    this._update(exports.Unit.seconds);
                    break;
                case 'calendar':
                    this._update(exports.Unit.date);
                    this._update(exports.Unit.year);
                    this._update(exports.Unit.month);
                    this.decadeDisplay._update(this.widget, this.paint);
                    this._updateCalendarHeader();
                    break;
                case 'all':
                    if (this._hasTime) {
                        this._update('clock');
                    }
                    if (this._hasDate) {
                        this._update('calendar');
                    }
            }
        }
        // noinspection JSUnusedLocalSymbols
        /**
         * Allows developers to add/remove classes from an element.
         * @param _unit
         * @param _date
         * @param _classes
         * @param _element
         */
        /* eslint-disable @typescript-eslint/no-unused-vars */
        paint(_unit, _date, _classes, _element) {
            // implemented in plugin
        }
        /* eslint-enable @typescript-eslint/no-unused-vars */
        /**
         * Shows the picker and creates a Popper instance if needed.
         * Add document click event to hide when clicking outside the picker.
         * fires Events#show
         */
        show() {
            if (this.widget == undefined) {
                if (this.dates.picked.length == 0) {
                    if (this.optionsStore.options.useCurrent &&
                        !this.optionsStore.options.defaultDate) {
                        const date = new DateTime().setLocale(this.optionsStore.options.localization.locale);
                        if (!this.optionsStore.options.keepInvalid) {
                            let tries = 0;
                            let direction = 1;
                            if (this.optionsStore.options.restrictions.maxDate?.isBefore(date)) {
                                direction = -1;
                            }
                            while (!this.validation.isValid(date)) {
                                date.manipulate(direction, exports.Unit.date);
                                if (tries > 31)
                                    break;
                                tries++;
                            }
                        }
                        this.dates.setValue(date);
                    }
                    if (this.optionsStore.options.defaultDate) {
                        this.dates.setValue(this.optionsStore.options.defaultDate);
                    }
                }
                this._buildWidget();
                this._updateTheme();
                // If modeView is only clock
                const onlyClock = this._hasTime && !this._hasDate;
                // reset the view to the clock if there's no date components
                if (onlyClock) {
                    this.optionsStore.currentView = 'clock';
                    this._eventEmitters.action.emit({
                        e: null,
                        action: ActionTypes$1.showClock,
                    });
                }
                // otherwise return to the calendar view
                else if (!this.optionsStore.currentCalendarViewMode) {
                    this.optionsStore.currentCalendarViewMode =
                        this.optionsStore.minimumCalendarViewMode;
                }
                if (!onlyClock &&
                    this.optionsStore.options.display.viewMode !== 'clock') {
                    if (this._hasTime) {
                        if (!this.optionsStore.options.display.sideBySide) {
                            Collapse.hideImmediately(this.widget.querySelector(`div.${Namespace.css.timeContainer}`));
                        }
                        else {
                            Collapse.show(this.widget.querySelector(`div.${Namespace.css.timeContainer}`));
                        }
                    }
                    Collapse.show(this.widget.querySelector(`div.${Namespace.css.dateContainer}`));
                }
                if (this._hasDate) {
                    this._showMode();
                }
                if (!this.optionsStore.options.display.inline) {
                    // If needed to change the parent container
                    const container = this.optionsStore.options?.container || document.body;
                    container.appendChild(this.widget);
                    this.createPopup(this.optionsStore.element, this.widget, {
                        modifiers: [{ name: 'eventListeners', enabled: true }],
                        //#2400
                        placement: document.documentElement.dir === 'rtl'
                            ? 'bottom-end'
                            : 'bottom-start',
                    }).then();
                }
                else {
                    this.optionsStore.element.appendChild(this.widget);
                }
                if (this.optionsStore.options.display.viewMode == 'clock') {
                    this._eventEmitters.action.emit({
                        e: null,
                        action: ActionTypes$1.showClock,
                    });
                }
                this.widget
                    .querySelectorAll('[data-action]')
                    .forEach((element) => element.addEventListener('click', this._actionsClickEvent));
                // show the clock when using sideBySide
                if (this._hasTime && this.optionsStore.options.display.sideBySide) {
                    this.timeDisplay._update(this.widget);
                    this.widget.getElementsByClassName(Namespace.css.clockContainer)[0].style.display = 'grid';
                }
            }
            this.widget.classList.add(Namespace.css.show);
            if (!this.optionsStore.options.display.inline) {
                this.updatePopup();
                document.addEventListener('click', this._documentClickEvent);
            }
            this._eventEmitters.triggerEvent.emit({ type: Namespace.events.show });
            this._isVisible = true;
        }
        async createPopup(element, widget, 
        //eslint-disable-next-line @typescript-eslint/no-explicit-any
        options) {
            let createPopperFunction;
            //eslint-disable-next-line @typescript-eslint/no-explicit-any
            if (window?.Popper) {
                //eslint-disable-next-line @typescript-eslint/no-explicit-any
                createPopperFunction = window?.Popper?.createPopper;
            }
            else {
                const { createPopper } = await import('@popperjs/core');
                createPopperFunction = createPopper;
            }
            if (createPopperFunction) {
                this._popperInstance = createPopperFunction(element, widget, options);
            }
        }
        updatePopup() {
            this._popperInstance?.update();
        }
        /**
         * Changes the calendar view mode. E.g. month <-> year
         * @param direction -/+ number to move currentViewMode
         * @private
         */
        _showMode(direction) {
            if (!this.widget) {
                return;
            }
            if (direction) {
                const max = Math.max(this.optionsStore.minimumCalendarViewMode, Math.min(3, this.optionsStore.currentCalendarViewMode + direction));
                if (this.optionsStore.currentCalendarViewMode == max)
                    return;
                this.optionsStore.currentCalendarViewMode = max;
            }
            this.widget
                .querySelectorAll(`.${Namespace.css.dateContainer} > div:not(.${Namespace.css.calendarHeader}), .${Namespace.css.timeContainer} > div:not(.${Namespace.css.clockContainer})`)
                .forEach((e) => (e.style.display = 'none'));
            const datePickerMode = CalendarModes[this.optionsStore.currentCalendarViewMode];
            const picker = this.widget.querySelector(`.${datePickerMode.className}`);
            switch (datePickerMode.className) {
                case Namespace.css.decadesContainer:
                    this.decadeDisplay._update(this.widget, this.paint);
                    break;
                case Namespace.css.yearsContainer:
                    this.yearDisplay._update(this.widget, this.paint);
                    break;
                case Namespace.css.monthsContainer:
                    this.monthDisplay._update(this.widget, this.paint);
                    break;
                case Namespace.css.daysContainer:
                    this.dateDisplay._update(this.widget, this.paint);
                    break;
            }
            picker.style.display = 'grid';
            if (this.optionsStore.options.display.sideBySide)
                (this.widget.querySelectorAll(`.${Namespace.css.clockContainer}`)[0]).style.display = 'grid';
            this._updateCalendarHeader();
            this._eventEmitters.viewUpdate.emit();
        }
        /**
         * Changes the theme. E.g. light, dark or auto
         * @param theme the theme name
         * @private
         */
        _updateTheme(theme) {
            if (!this.widget) {
                return;
            }
            if (theme) {
                if (this.optionsStore.options.display.theme === theme)
                    return;
                this.optionsStore.options.display.theme = theme;
            }
            this.widget.classList.remove('light', 'dark');
            this.widget.classList.add(this._getThemeClass());
            if (this.optionsStore.options.display.theme === 'auto') {
                window
                    .matchMedia(Namespace.css.isDarkPreferredQuery)
                    .addEventListener('change', () => this._updateTheme());
            }
            else {
                window
                    .matchMedia(Namespace.css.isDarkPreferredQuery)
                    .removeEventListener('change', () => this._updateTheme());
            }
        }
        _getThemeClass() {
            const currentTheme = this.optionsStore.options.display.theme || 'auto';
            const isDarkMode = window.matchMedia &&
                window.matchMedia(Namespace.css.isDarkPreferredQuery).matches;
            switch (currentTheme) {
                case 'light':
                    return Namespace.css.lightTheme;
                case 'dark':
                    return Namespace.css.darkTheme;
                case 'auto':
                    return isDarkMode ? Namespace.css.darkTheme : Namespace.css.lightTheme;
            }
        }
        _updateCalendarHeader() {
            if (!this._hasDate)
                return;
            const showing = [
                ...this.widget.querySelector(`.${Namespace.css.dateContainer} div[style*="display: grid"]`).classList,
            ].find((x) => x.startsWith(Namespace.css.dateContainer));
            const [previous, switcher, next] = this.widget
                .getElementsByClassName(Namespace.css.calendarHeader)[0]
                .getElementsByTagName('div');
            switch (showing) {
                case Namespace.css.decadesContainer:
                    previous.setAttribute('title', this.optionsStore.options.localization.previousCentury);
                    switcher.setAttribute('title', '');
                    next.setAttribute('title', this.optionsStore.options.localization.nextCentury);
                    break;
                case Namespace.css.yearsContainer:
                    previous.setAttribute('title', this.optionsStore.options.localization.previousDecade);
                    switcher.setAttribute('title', this.optionsStore.options.localization.selectDecade);
                    next.setAttribute('title', this.optionsStore.options.localization.nextDecade);
                    break;
                case Namespace.css.monthsContainer:
                    previous.setAttribute('title', this.optionsStore.options.localization.previousYear);
                    switcher.setAttribute('title', this.optionsStore.options.localization.selectYear);
                    next.setAttribute('title', this.optionsStore.options.localization.nextYear);
                    break;
                case Namespace.css.daysContainer:
                    previous.setAttribute('title', this.optionsStore.options.localization.previousMonth);
                    switcher.setAttribute('title', this.optionsStore.options.localization.selectMonth);
                    next.setAttribute('title', this.optionsStore.options.localization.nextMonth);
                    switcher.setAttribute(showing, this.optionsStore.viewDate.format(this.optionsStore.options.localization.dayViewHeaderFormat));
                    break;
            }
            switcher.innerText = switcher.getAttribute(showing);
        }
        /**
         * Hides the picker if needed.
         * Remove document click event to hide when clicking outside the picker.
         * fires Events#hide
         */
        hide() {
            if (!this.widget || !this._isVisible)
                return;
            this.widget.classList.remove(Namespace.css.show);
            if (this._isVisible) {
                this._eventEmitters.triggerEvent.emit({
                    type: Namespace.events.hide,
                    date: this.optionsStore.unset
                        ? null
                        : this.dates.lastPicked
                            ? this.dates.lastPicked.clone
                            : void 0,
                });
                this._isVisible = false;
            }
            document.removeEventListener('click', this._documentClickEvent);
        }
        /**
         * Toggles the picker's open state. Fires a show/hide event depending.
         */
        toggle() {
            return this._isVisible ? this.hide() : this.show();
        }
        /**
         * Removes document and data-action click listener and reset the widget
         * @private
         */
        _dispose() {
            document.removeEventListener('click', this._documentClickEvent);
            if (!this.widget)
                return;
            this.widget
                .querySelectorAll('[data-action]')
                .forEach((element) => element.removeEventListener('click', this._actionsClickEvent));
            this.widget.parentNode.removeChild(this.widget);
            this._widget = undefined;
        }
        /**
         * Builds the widgets html template.
         * @private
         */
        _buildWidget() {
            const template = document.createElement('div');
            template.classList.add(Namespace.css.widget);
            const dateView = document.createElement('div');
            dateView.classList.add(Namespace.css.dateContainer);
            dateView.append(this.getHeadTemplate(), this.decadeDisplay.getPicker(), this.yearDisplay.getPicker(), this.monthDisplay.getPicker(), this.dateDisplay.getPicker());
            const timeView = document.createElement('div');
            timeView.classList.add(Namespace.css.timeContainer);
            timeView.appendChild(this.timeDisplay.getPicker(this._iconTag.bind(this)));
            timeView.appendChild(this.hourDisplay.getPicker());
            timeView.appendChild(this.minuteDisplay.getPicker());
            timeView.appendChild(this.secondDisplay.getPicker());
            const toolbar = document.createElement('div');
            toolbar.classList.add(Namespace.css.toolbar);
            toolbar.append(...this.getToolbarElements());
            if (this.optionsStore.options.display.inline) {
                template.classList.add(Namespace.css.inline);
            }
            if (this.optionsStore.options.display.calendarWeeks) {
                template.classList.add('calendarWeeks');
            }
            if (this.optionsStore.options.display.sideBySide &&
                this._hasDate &&
                this._hasTime) {
                template.classList.add(Namespace.css.sideBySide);
                if (this.optionsStore.options.display.toolbarPlacement === 'top') {
                    template.appendChild(toolbar);
                }
                const row = document.createElement('div');
                row.classList.add('td-row');
                dateView.classList.add('td-half');
                timeView.classList.add('td-half');
                row.appendChild(dateView);
                row.appendChild(timeView);
                template.appendChild(row);
                if (this.optionsStore.options.display.toolbarPlacement === 'bottom') {
                    template.appendChild(toolbar);
                }
                this._widget = template;
                return;
            }
            if (this.optionsStore.options.display.toolbarPlacement === 'top') {
                template.appendChild(toolbar);
            }
            if (this._hasDate) {
                if (this._hasTime) {
                    dateView.classList.add(Namespace.css.collapse);
                    if (this.optionsStore.options.display.viewMode !== 'clock')
                        dateView.classList.add(Namespace.css.show);
                }
                template.appendChild(dateView);
            }
            if (this._hasTime) {
                if (this._hasDate) {
                    timeView.classList.add(Namespace.css.collapse);
                    if (this.optionsStore.options.display.viewMode === 'clock')
                        timeView.classList.add(Namespace.css.show);
                }
                template.appendChild(timeView);
            }
            if (this.optionsStore.options.display.toolbarPlacement === 'bottom') {
                template.appendChild(toolbar);
            }
            const arrow = document.createElement('div');
            arrow.classList.add('arrow');
            arrow.setAttribute('data-popper-arrow', '');
            template.appendChild(arrow);
            this._widget = template;
        }
        /**
         * Returns true if the hours, minutes, or seconds component is turned on
         */
        get _hasTime() {
            return (this.optionsStore.options.display.components.clock &&
                (this.optionsStore.options.display.components.hours ||
                    this.optionsStore.options.display.components.minutes ||
                    this.optionsStore.options.display.components.seconds));
        }
        /**
         * Returns true if the year, month, or date component is turned on
         */
        get _hasDate() {
            return (this.optionsStore.options.display.components.calendar &&
                (this.optionsStore.options.display.components.year ||
                    this.optionsStore.options.display.components.month ||
                    this.optionsStore.options.display.components.date));
        }
        /**
         * Get the toolbar html based on options like buttons.today
         * @private
         */
        getToolbarElements() {
            const toolbar = [];
            if (this.optionsStore.options.display.buttons.today) {
                const div = document.createElement('div');
                div.setAttribute('data-action', ActionTypes$1.today);
                div.setAttribute('title', this.optionsStore.options.localization.today);
                div.appendChild(this._iconTag(this.optionsStore.options.display.icons.today));
                toolbar.push(div);
            }
            if (!this.optionsStore.options.display.sideBySide &&
                this._hasDate &&
                this._hasTime) {
                let title, icon;
                if (this.optionsStore.options.display.viewMode === 'clock') {
                    title = this.optionsStore.options.localization.selectDate;
                    icon = this.optionsStore.options.display.icons.date;
                }
                else {
                    title = this.optionsStore.options.localization.selectTime;
                    icon = this.optionsStore.options.display.icons.time;
                }
                const div = document.createElement('div');
                div.setAttribute('data-action', ActionTypes$1.togglePicker);
                div.setAttribute('title', title);
                div.appendChild(this._iconTag(icon));
                toolbar.push(div);
            }
            if (this.optionsStore.options.display.buttons.clear) {
                const div = document.createElement('div');
                div.setAttribute('data-action', ActionTypes$1.clear);
                div.setAttribute('title', this.optionsStore.options.localization.clear);
                div.appendChild(this._iconTag(this.optionsStore.options.display.icons.clear));
                toolbar.push(div);
            }
            if (this.optionsStore.options.display.buttons.close) {
                const div = document.createElement('div');
                div.setAttribute('data-action', ActionTypes$1.close);
                div.setAttribute('title', this.optionsStore.options.localization.close);
                div.appendChild(this._iconTag(this.optionsStore.options.display.icons.close));
                toolbar.push(div);
            }
            return toolbar;
        }
        /***
         * Builds the base header template with next and previous icons
         * @private
         */
        getHeadTemplate() {
            const calendarHeader = document.createElement('div');
            calendarHeader.classList.add(Namespace.css.calendarHeader);
            const previous = document.createElement('div');
            previous.classList.add(Namespace.css.previous);
            previous.setAttribute('data-action', ActionTypes$1.previous);
            previous.appendChild(this._iconTag(this.optionsStore.options.display.icons.previous));
            const switcher = document.createElement('div');
            switcher.classList.add(Namespace.css.switch);
            switcher.setAttribute('data-action', ActionTypes$1.changeCalendarView);
            const next = document.createElement('div');
            next.classList.add(Namespace.css.next);
            next.setAttribute('data-action', ActionTypes$1.next);
            next.appendChild(this._iconTag(this.optionsStore.options.display.icons.next));
            calendarHeader.append(previous, switcher, next);
            return calendarHeader;
        }
        /**
         * Builds an icon tag as either an `<i>`
         * or with icons.type is `sprites` then a svg tag instead
         * @param iconClass
         * @private
         */
        _iconTag(iconClass) {
            if (this.optionsStore.options.display.icons.type === 'sprites') {
                const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
                const icon = document.createElementNS('http://www.w3.org/2000/svg', 'use');
                icon.setAttribute('xlink:href', iconClass); // Deprecated. Included for backward compatibility
                icon.setAttribute('href', iconClass);
                const svgclass = iconClass.slice(1) + "-tempus-dominus " + "tempus-dominus-svg";
                svg.setAttributeNS(null, "class", svgclass);
                svg.appendChild(icon);
                return svg;
            }
            const icon = document.createElement('i');
            icon.classList.add(...iconClass.split(' '));
            return icon;
        }
        /**
         * Causes the widget to get rebuilt on next show. If the picker is already open
         * then hide and reshow it.
         * @private
         */
        _rebuild() {
            const wasVisible = this._isVisible;
            this._dispose();
            if (wasVisible)
                this.show();
        }
    }
  
    /**
     *
     */
    class Actions {
        constructor() {
            this.optionsStore = serviceLocator.locate(OptionsStore);
            this.dates = serviceLocator.locate(Dates);
            this.validation = serviceLocator.locate(Validation);
            this.display = serviceLocator.locate(Display);
            this._eventEmitters = serviceLocator.locate(EventEmitters);
            this._eventEmitters.action.subscribe((result) => {
                this.do(result.e, result.action);
            });
        }
        /**
         * Performs the selected `action`. See ActionTypes
         * @param e This is normally a click event
         * @param action If not provided, then look for a [data-action]
         */
        //eslint-disable-next-line @typescript-eslint/no-explicit-any
        do(e, action) {
            const currentTarget = e?.currentTarget;
            if (currentTarget?.classList?.contains(Namespace.css.disabled))
                return false;
            action = action || currentTarget?.dataset?.action;
            const lastPicked = (this.dates.lastPicked || this.optionsStore.viewDate)
                .clone;
            switch (action) {
                case ActionTypes$1.next:
                case ActionTypes$1.previous:
                    this.handleNextPrevious(action);
                    break;
                case ActionTypes$1.changeCalendarView:
                    this.display._showMode(1);
                    this.display._updateCalendarHeader();
                    break;
                case ActionTypes$1.selectMonth:
                case ActionTypes$1.selectYear:
                case ActionTypes$1.selectDecade:
                    this.handleSelectCalendarMode(action, currentTarget);
                    break;
                case ActionTypes$1.selectDay:
                    this.handleSelectDay(currentTarget);
                    break;
                case ActionTypes$1.selectHour: {
                    let hour = +currentTarget.dataset.value;
                    if (lastPicked.hours >= 12 && this.optionsStore.isTwelveHour)
                        hour += 12;
                    lastPicked.hours = hour;
                    this.dates.setValue(lastPicked, this.dates.lastPickedIndex);
                    this.hideOrClock(e);
                    break;
                }
                case ActionTypes$1.selectMinute: {
                    lastPicked.minutes = +currentTarget.dataset.value;
                    this.dates.setValue(lastPicked, this.dates.lastPickedIndex);
                    this.hideOrClock(e);
                    break;
                }
                case ActionTypes$1.selectSecond: {
                    lastPicked.seconds = +currentTarget.dataset.value;
                    this.dates.setValue(lastPicked, this.dates.lastPickedIndex);
                    this.hideOrClock(e);
                    break;
                }
                case ActionTypes$1.incrementHours:
                    this.manipulateAndSet(lastPicked, exports.Unit.hours);
                    break;
                case ActionTypes$1.incrementMinutes:
                    this.manipulateAndSet(lastPicked, exports.Unit.minutes, this.optionsStore.options.stepping);
                    break;
                case ActionTypes$1.incrementSeconds:
                    this.manipulateAndSet(lastPicked, exports.Unit.seconds);
                    break;
                case ActionTypes$1.decrementHours:
                    this.manipulateAndSet(lastPicked, exports.Unit.hours, -1);
                    break;
                case ActionTypes$1.decrementMinutes:
                    this.manipulateAndSet(lastPicked, exports.Unit.minutes, this.optionsStore.options.stepping * -1);
                    break;
                case ActionTypes$1.decrementSeconds:
                    this.manipulateAndSet(lastPicked, exports.Unit.seconds, -1);
                    break;
                case ActionTypes$1.toggleMeridiem:
                    this.manipulateAndSet(lastPicked, exports.Unit.hours, this.dates.lastPicked.hours >= 12 ? -12 : 12);
                    break;
                case ActionTypes$1.togglePicker:
                    this.handleToggle(currentTarget);
                    break;
                case ActionTypes$1.showClock:
                case ActionTypes$1.showHours:
                case ActionTypes$1.showMinutes:
                case ActionTypes$1.showSeconds:
                    //make sure the clock is actually displaying
                    if (!this.optionsStore.options.display.sideBySide &&
                        this.optionsStore.currentView !== 'clock') {
                        //hide calendar
                        Collapse.hideImmediately(this.display.widget.querySelector(`div.${Namespace.css.dateContainer}`));
                        //show clock
                        Collapse.showImmediately(this.display.widget.querySelector(`div.${Namespace.css.timeContainer}`));
                    }
                    this.handleShowClockContainers(action);
                    break;
                case ActionTypes$1.clear:
                    this.dates.setValue(null);
                    this.display._updateCalendarHeader();
                    break;
                case ActionTypes$1.close:
                    this.display.hide();
                    break;
                case ActionTypes$1.today: {
                    const today = new DateTime().setLocale(this.optionsStore.options.localization.locale);
                    this._eventEmitters.updateViewDate.emit(today);
                    //todo this this really a good idea?
                    if (this.validation.isValid(today, exports.Unit.date))
                        this.dates.setValue(today, this.dates.lastPickedIndex);
                    break;
                }
            }
        }
        handleShowClockContainers(action) {
            if (!this.display._hasTime) {
                Namespace.errorMessages.throwError('Cannot show clock containers when time is disabled.');
                return;
            }
            this.optionsStore.currentView = 'clock';
            this.display.widget
                .querySelectorAll(`.${Namespace.css.timeContainer} > div`)
                .forEach((htmlElement) => (htmlElement.style.display = 'none'));
            let classToUse = '';
            switch (action) {
                case ActionTypes$1.showClock:
                    classToUse = Namespace.css.clockContainer;
                    this.display._update('clock');
                    break;
                case ActionTypes$1.showHours:
                    classToUse = Namespace.css.hourContainer;
                    this.display._update(exports.Unit.hours);
                    break;
                case ActionTypes$1.showMinutes:
                    classToUse = Namespace.css.minuteContainer;
                    this.display._update(exports.Unit.minutes);
                    break;
                case ActionTypes$1.showSeconds:
                    classToUse = Namespace.css.secondContainer;
                    this.display._update(exports.Unit.seconds);
                    break;
            }
            (this.display.widget.getElementsByClassName(classToUse)[0]).style.display = 'grid';
        }
        handleNextPrevious(action) {
            const { unit, step } = CalendarModes[this.optionsStore.currentCalendarViewMode];
            if (action === ActionTypes$1.next)
                this.optionsStore.viewDate.manipulate(step, unit);
            else
                this.optionsStore.viewDate.manipulate(step * -1, unit);
            this._eventEmitters.viewUpdate.emit();
            this.display._showMode();
        }
        /**
         * After setting the value it will either show the clock or hide the widget.
         * @param e
         */
        hideOrClock(e) {
            if (!this.optionsStore.isTwelveHour &&
                !this.optionsStore.options.display.components.minutes &&
                !this.optionsStore.options.display.keepOpen &&
                !this.optionsStore.options.display.inline) {
                this.display.hide();
            }
            else {
                this.do(e, ActionTypes$1.showClock);
            }
        }
        /**
         * Common function to manipulate {@link lastPicked} by `unit`.
         * @param lastPicked
         * @param unit
         * @param value Value to change by
         */
        manipulateAndSet(lastPicked, unit, value = 1) {
            const newDate = lastPicked.manipulate(value, unit);
            if (this.validation.isValid(newDate, unit)) {
                this.dates.setValue(newDate, this.dates.lastPickedIndex);
            }
        }
        handleSelectCalendarMode(action, 
        //eslint-disable-next-line @typescript-eslint/no-explicit-any
        currentTarget) {
            const value = +currentTarget.dataset.value;
            switch (action) {
                case ActionTypes$1.selectMonth:
                    this.optionsStore.viewDate.month = value;
                    break;
                case ActionTypes$1.selectYear:
                case ActionTypes$1.selectDecade:
                    this.optionsStore.viewDate.year = value;
                    break;
            }
            if (this.optionsStore.currentCalendarViewMode ===
                this.optionsStore.minimumCalendarViewMode) {
                this.dates.setValue(this.optionsStore.viewDate, this.dates.lastPickedIndex);
                if (!this.optionsStore.options.display.inline) {
                    this.display.hide();
                }
            }
            else {
                this.display._showMode(-1);
            }
        }
        //eslint-disable-next-line @typescript-eslint/no-explicit-any
        handleToggle(currentTarget) {
            if (currentTarget.getAttribute('title') ===
                this.optionsStore.options.localization.selectDate) {
                currentTarget.setAttribute('title', this.optionsStore.options.localization.selectTime);
                currentTarget.innerHTML = this.display._iconTag(this.optionsStore.options.display.icons.time).outerHTML;
                this.display._updateCalendarHeader();
                this.optionsStore.refreshCurrentView();
            }
            else {
                currentTarget.setAttribute('title', this.optionsStore.options.localization.selectDate);
                currentTarget.innerHTML = this.display._iconTag(this.optionsStore.options.display.icons.date).outerHTML;
                if (this.display._hasTime) {
                    this.handleShowClockContainers(ActionTypes$1.showClock);
                    this.display._update('clock');
                }
            }
            this.display.widget
                .querySelectorAll(`.${Namespace.css.dateContainer}, .${Namespace.css.timeContainer}`)
                .forEach((htmlElement) => Collapse.toggle(htmlElement));
            this._eventEmitters.viewUpdate.emit();
        }
        //eslint-disable-next-line @typescript-eslint/no-explicit-any
        handleSelectDay(currentTarget) {
            const day = this.optionsStore.viewDate.clone;
            if (currentTarget.classList.contains(Namespace.css.old)) {
                day.manipulate(-1, exports.Unit.month);
            }
            if (currentTarget.classList.contains(Namespace.css.new)) {
                day.manipulate(1, exports.Unit.month);
            }
            day.date = +currentTarget.dataset.day;
            let index = 0;
            if (this.optionsStore.options.multipleDates) {
                index = this.dates.pickedIndex(day, exports.Unit.date);
                if (index !== -1) {
                    this.dates.setValue(null, index); //deselect multi-date
                }
                else {
                    this.dates.setValue(day, this.dates.lastPickedIndex + 1);
                }
            }
            else {
                this.dates.setValue(day, this.dates.lastPickedIndex);
            }
            if (!this.display._hasTime &&
                !this.optionsStore.options.display.keepOpen &&
                !this.optionsStore.options.display.inline &&
                !this.optionsStore.options.multipleDates) {
                this.display.hide();
            }
        }
    }
  
    /**
     * A robust and powerful date/time picker component.
     */
    class TempusDominus {
        constructor(element, options = {}) {
            //eslint-disable-next-line @typescript-eslint/no-explicit-any
            this._subscribers = {};
            this._isDisabled = false;
            /**
             * Event for when the input field changes. This is a class level method so there's
             * something for the remove listener function.
             * @private
             */
            //eslint-disable-next-line @typescript-eslint/no-explicit-any
            this._inputChangeEvent = (event) => {
                const internallyTriggered = event?.detail;
                if (internallyTriggered)
                    return;
                const setViewDate = () => {
                    if (this.dates.lastPicked)
                        this.optionsStore.viewDate = this.dates.lastPicked.clone;
                };
                const value = this.optionsStore.input.value;
                if (this.optionsStore.options.multipleDates) {
                    try {
                        const valueSplit = value.split(this.optionsStore.options.multipleDatesSeparator);
                        for (let i = 0; i < valueSplit.length; i++) {
                            this.dates.setFromInput(valueSplit[i], i);
                        }
                        setViewDate();
                    }
                    catch {
                        console.warn('TD: Something went wrong trying to set the multipleDates values from the input field.');
                    }
                }
                else {
                    this.dates.setFromInput(value, 0);
                    setViewDate();
                }
            };
            /**
             * Event for when the toggle is clicked. This is a class level method so there's
             * something for the remove listener function.
             * @private
             */
            this._toggleClickEvent = () => {
                if (this.optionsStore.element?.disabled ||
                    this.optionsStore.input?.disabled)
                    return;
                this.toggle();
            };
            setupServiceLocator();
            this._eventEmitters = serviceLocator.locate(EventEmitters);
            this.optionsStore = serviceLocator.locate(OptionsStore);
            this.display = serviceLocator.locate(Display);
            this.dates = serviceLocator.locate(Dates);
            this.actions = serviceLocator.locate(Actions);
            if (!element) {
                Namespace.errorMessages.mustProvideElement();
            }
            this.optionsStore.element = element;
            this._initializeOptions(options, DefaultOptions, true);
            this.optionsStore.viewDate.setLocale(this.optionsStore.options.localization.locale);
            this.optionsStore.unset = true;
            this._initializeInput();
            this._initializeToggle();
            if (this.optionsStore.options.display.inline)
                this.display.show();
            this._eventEmitters.triggerEvent.subscribe((e) => {
                this._triggerEvent(e);
            });
            this._eventEmitters.viewUpdate.subscribe(() => {
                this._viewUpdate();
            });
            this._eventEmitters.updateViewDate.subscribe((dateTime) => {
                this.viewDate = dateTime;
            });
        }
        get viewDate() {
            return this.optionsStore.viewDate;
        }
        set viewDate(value) {
            this.optionsStore.viewDate = value;
            this.optionsStore.viewDate.setLocale(this.optionsStore.options.localization.locale);
            this.display._update(this.optionsStore.currentView === 'clock' ? 'clock' : 'calendar');
        }
        // noinspection JSUnusedGlobalSymbols
        /**
         * Update the picker options. If `reset` is provide `options` will be merged with DefaultOptions instead.
         * @param options
         * @param reset
         * @public
         */
        updateOptions(options, reset = false) {
            if (reset)
                this._initializeOptions(options, DefaultOptions);
            else
                this._initializeOptions(options, this.optionsStore.options);
            this.display._rebuild();
        }
        // noinspection JSUnusedGlobalSymbols
        /**
         * Toggles the picker open or closed. If the picker is disabled, nothing will happen.
         * @public
         */
        toggle() {
            if (this._isDisabled)
                return;
            this.display.toggle();
        }
        // noinspection JSUnusedGlobalSymbols
        /**
         * Shows the picker unless the picker is disabled.
         * @public
         */
        show() {
            if (this._isDisabled)
                return;
            this.display.show();
        }
        // noinspection JSUnusedGlobalSymbols
        /**
         * Hides the picker unless the picker is disabled.
         * @public
         */
        hide() {
            this.display.hide();
        }
        // noinspection JSUnusedGlobalSymbols
        /**
         * Disables the picker and the target input field.
         * @public
         */
        disable() {
            this._isDisabled = true;
            // todo this might be undesired. If a dev disables the input field to
            // only allow using the picker, this will break that.
            this.optionsStore.input?.setAttribute('disabled', 'disabled');
            this.display.hide();
        }
        // noinspection JSUnusedGlobalSymbols
        /**
         * Enables the picker and the target input field.
         * @public
         */
        enable() {
            this._isDisabled = false;
            this.optionsStore.input?.removeAttribute('disabled');
        }
        // noinspection JSUnusedGlobalSymbols
        /**
         * Clears all the selected dates
         * @public
         */
        clear() {
            this.optionsStore.input.value = '';
            this.dates.clear();
        }
        // noinspection JSUnusedGlobalSymbols
        /**
         * Allows for a direct subscription to picker events, without having to use addEventListener on the element.
         * @param eventTypes See Namespace.Events
         * @param callbacks Function to call when event is triggered
         * @public
         */
        subscribe(eventTypes, callbacks //eslint-disable-line @typescript-eslint/no-explicit-any
        ) {
            if (typeof eventTypes === 'string') {
                eventTypes = [eventTypes];
            }
            let callBackArray; //eslint-disable-line @typescript-eslint/no-explicit-any
            if (!Array.isArray(callbacks)) {
                callBackArray = [callbacks];
            }
            else {
                callBackArray = callbacks;
            }
            if (eventTypes.length !== callBackArray.length) {
                Namespace.errorMessages.subscribeMismatch();
            }
            const returnArray = [];
            for (let i = 0; i < eventTypes.length; i++) {
                const eventType = eventTypes[i];
                if (!Array.isArray(this._subscribers[eventType])) {
                    this._subscribers[eventType] = [];
                }
                this._subscribers[eventType].push(callBackArray[i]);
                returnArray.push({
                    unsubscribe: this._unsubscribe.bind(this, eventType, this._subscribers[eventType].length - 1),
                });
                if (eventTypes.length === 1) {
                    return returnArray[0];
                }
            }
            return returnArray;
        }
        // noinspection JSUnusedGlobalSymbols
        /**
         * Hides the picker and removes event listeners
         */
        dispose() {
            this.display.hide();
            // this will clear the document click event listener
            this.display._dispose();
            this._eventEmitters.destroy();
            this.optionsStore.input?.removeEventListener('change', this._inputChangeEvent);
            if (this.optionsStore.options.allowInputToggle) {
                this.optionsStore.input?.removeEventListener('click', this._toggleClickEvent);
            }
            this._toggle?.removeEventListener('click', this._toggleClickEvent);
            this._subscribers = {};
        }
        /**
         * Updates the options to use the provided language.
         * THe language file must be loaded first.
         * @param language
         */
        locale(language) {
            const asked = loadedLocales[language];
            if (!asked)
                return;
            this.updateOptions({
                localization: asked,
            });
        }
        /**
         * Triggers an event like ChangeEvent when the picker has updated the value
         * of a selected date.
         * @param event Accepts a BaseEvent object.
         * @private
         */
        _triggerEvent(event) {
            event.viewMode = this.optionsStore.currentView;
            const isChangeEvent = event.type === Namespace.events.change;
            if (isChangeEvent) {
                const { date, oldDate, isClear } = event;
                if ((date && oldDate && date.isSame(oldDate)) ||
                    (!isClear && !date && !oldDate)) {
                    return;
                }
                this._handleAfterChangeEvent(event);
                this.optionsStore.input?.dispatchEvent(
                //eslint-disable-next-line @typescript-eslint/no-explicit-any
                new CustomEvent(event.type, { detail: event }));
                this.optionsStore.input?.dispatchEvent(
                //eslint-disable-next-line @typescript-eslint/no-explicit-any
                new CustomEvent('change', { detail: event }));
            }
            this.optionsStore.element.dispatchEvent(
            //eslint-disable-next-line @typescript-eslint/no-explicit-any
            new CustomEvent(event.type, { detail: event }));
            //eslint-disable-next-line @typescript-eslint/no-explicit-any
            if (window.jQuery) {
                //eslint-disable-next-line @typescript-eslint/no-explicit-any
                const $ = window.jQuery;
                if (isChangeEvent && this.optionsStore.input) {
                    $(this.optionsStore.input).trigger(event);
                }
                else {
                    $(this.optionsStore.element).trigger(event);
                }
            }
            this._publish(event);
        }
        _publish(event) {
            // return if event is not subscribed
            if (!Array.isArray(this._subscribers[event.type])) {
                return;
            }
            // Trigger callback for each subscriber
            this._subscribers[event.type].forEach((callback) => {
                callback(event);
            });
        }
        /**
         * Fires a ViewUpdate event when, for example, the month view is changed.
         * @private
         */
        _viewUpdate() {
            this._triggerEvent({
                type: Namespace.events.update,
                viewDate: this.optionsStore.viewDate.clone,
            });
        }
        _unsubscribe(eventName, index) {
            this._subscribers[eventName].splice(index, 1);
        }
        /**
         * Merges two Option objects together and validates options type
         * @param config new Options
         * @param mergeTo Options to merge into
         * @param includeDataset When true, the elements data-td attributes will be included in the
         * @private
         */
        _initializeOptions(config, mergeTo, includeDataset = false) {
            let newConfig = OptionConverter.deepCopy(config);
            newConfig = OptionConverter._mergeOptions(newConfig, mergeTo);
            if (includeDataset)
                newConfig = OptionConverter._dataToOptions(this.optionsStore.element, newConfig);
            OptionConverter._validateConflicts(newConfig);
            newConfig.viewDate = newConfig.viewDate.setLocale(newConfig.localization.locale);
            if (!this.optionsStore.viewDate.isSame(newConfig.viewDate)) {
                this.optionsStore.viewDate = newConfig.viewDate;
            }
            /**
             * Sets the minimum view allowed by the picker. For example the case of only
             * allowing year and month to be selected but not date.
             */
            if (newConfig.display.components.year) {
                this.optionsStore.minimumCalendarViewMode = 2;
            }
            if (newConfig.display.components.month) {
                this.optionsStore.minimumCalendarViewMode = 1;
            }
            if (newConfig.display.components.date) {
                this.optionsStore.minimumCalendarViewMode = 0;
            }
            this.optionsStore.currentCalendarViewMode = Math.max(this.optionsStore.minimumCalendarViewMode, this.optionsStore.currentCalendarViewMode);
            // Update view mode if needed
            if (CalendarModes[this.optionsStore.currentCalendarViewMode].name !==
                newConfig.display.viewMode) {
                this.optionsStore.currentCalendarViewMode = Math.max(CalendarModes.findIndex((x) => x.name === newConfig.display.viewMode), this.optionsStore.minimumCalendarViewMode);
            }
            if (this.display?.isVisible) {
                this.display._update('all');
            }
            if (newConfig.display.components.useTwentyfourHour &&
                newConfig.localization.hourCycle === undefined)
                newConfig.localization.hourCycle = 'h24';
            else if (newConfig.localization.hourCycle === undefined) {
                newConfig.localization.hourCycle = guessHourCycle(newConfig.localization.locale);
            }
            this.optionsStore.options = newConfig;
        }
        /**
         * Checks if an input field is being used, attempts to locate one and sets an
         * event listener if found.
         * @private
         */
        _initializeInput() {
            if (this.optionsStore.element.tagName == 'INPUT') {
                this.optionsStore.input = this.optionsStore.element;
            }
            else {
                const query = this.optionsStore.element.dataset.tdTargetInput;
                if (query == undefined || query == 'nearest') {
                    this.optionsStore.input =
                        this.optionsStore.element.querySelector('input');
                }
                else {
                    this.optionsStore.input =
                        this.optionsStore.element.querySelector(query);
                }
            }
            if (!this.optionsStore.input)
                return;
            if (!this.optionsStore.input.value && this.optionsStore.options.defaultDate)
                this.optionsStore.input.value = this.dates.formatInput(this.optionsStore.options.defaultDate);
            this.optionsStore.input.addEventListener('change', this._inputChangeEvent);
            if (this.optionsStore.options.allowInputToggle) {
                this.optionsStore.input.addEventListener('click', this._toggleClickEvent);
            }
            if (this.optionsStore.input.value) {
                this._inputChangeEvent();
            }
        }
        /**
         * Attempts to locate a toggle for the picker and sets an event listener
         * @private
         */
        _initializeToggle() {
            if (this.optionsStore.options.display.inline)
                return;
            let query = this.optionsStore.element.dataset.tdTargetToggle;
            if (query == 'nearest') {
                query = '[data-td-toggle="datetimepicker"]';
            }
            this._toggle =
                query == undefined
                    ? this.optionsStore.element
                    : this.optionsStore.element.querySelector(query);
            this._toggle.addEventListener('click', this._toggleClickEvent);
        }
        /**
         * If the option is enabled this will render the clock view after a date pick.
         * @param e change event
         * @private
         */
        _handleAfterChangeEvent(e) {
            if (
            // options is disabled
            !this.optionsStore.options.promptTimeOnDateChange ||
                this.optionsStore.options.display.inline ||
                this.optionsStore.options.display.sideBySide ||
                // time is disabled
                !this.display._hasTime ||
                // clock component is already showing
                this.display.widget
                    ?.getElementsByClassName(Namespace.css.show)[0]
                    .classList.contains(Namespace.css.timeContainer))
                return;
            // First time ever. If useCurrent option is set to true (default), do nothing
            // because the first date is selected automatically.
            // or date didn't change (time did) or date changed because time did.
            if ((!e.oldDate && this.optionsStore.options.useCurrent) ||
                (e.oldDate && e.date?.isSame(e.oldDate))) {
                return;
            }
            clearTimeout(this._currentPromptTimeTimeout);
            this._currentPromptTimeTimeout = setTimeout(() => {
                if (this.display.widget) {
                    this._eventEmitters.action.emit({
                        e: {
                            currentTarget: this.display.widget.querySelector(`.${Namespace.css.switch}`),
                        },
                        action: ActionTypes$1.togglePicker,
                    });
                }
            }, this.optionsStore.options.promptTimeOnDateChangeTransitionDelay);
        }
    }
    /**
     * Whenever a locale is loaded via a plugin then store it here based on the
     * locale name. E.g. loadedLocales['ru']
     */
    const loadedLocales = {};
    // noinspection JSUnusedGlobalSymbols
    /**
     * Called from a locale plugin.
     * @param l locale object for localization options
     */
    const loadLocale = (l) => {
        if (loadedLocales[l.name])
            return;
        loadedLocales[l.name] = l.localization;
    };
    /**
     * A sets the global localization options to the provided locale name.
     * `loadLocale` MUST be called first.
     * @param l
     */
    const locale = (l) => {
        const asked = loadedLocales[l];
        if (!asked)
            return;
        DefaultOptions.localization = asked;
    };
    // noinspection JSUnusedGlobalSymbols
    /**
     * Called from a plugin to extend or override picker defaults.
     * @param plugin
     * @param option
     */
    const extend = function (plugin, option = undefined) {
        if (!plugin)
            return tempusDominus;
        if (!plugin.installed) {
            // install plugin only once
            plugin(option, { TempusDominus, Dates, Display, DateTime, Namespace }, tempusDominus);
            plugin.installed = true;
        }
        return tempusDominus;
    };
    const version = '6.2.10';
    const tempusDominus = {
        TempusDominus,
        extend,
        loadLocale,
        locale,
        Namespace,
        DefaultOptions,
        DateTime,
        Unit: exports.Unit,
        version,
    };
  
    exports.DateTime = DateTime;
    exports.DefaultOptions = DefaultOptions;
    exports.Namespace = Namespace;
    exports.TempusDominus = TempusDominus;
    exports.extend = extend;
    exports.loadLocale = loadLocale;
    exports.locale = locale;
    exports.version = version;
  
    Object.defineProperty(exports, '__esModule', { value: true });
  
  }));
  //# sourceMappingURL=tempus-dominus.js.map
  