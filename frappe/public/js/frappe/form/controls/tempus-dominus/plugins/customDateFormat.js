/*!
  * Tempus Dominus v6.2.10 (https://getdatepicker.com/)
  * Copyright 2013-2022 Jonathan Peterson
  * Licensed under MIT (https://github.com/Eonasdan/tempus-dominus/blob/master/LICENSE)
  */
(function(g,f){typeof exports==='object'&&typeof module!=='undefined'?module.exports=f():typeof define==='function'&&define.amd?define(f):(g=typeof globalThis!=='undefined'?globalThis:g||self,(g.tempusDominus=g.tempusDominus||{},g.tempusDominus.plugins=g.tempusDominus.plugins||{},g.tempusDominus.plugins.customDateFormat=f()));})(this,(function(){'use strict';class CustomDateFormat {
    constructor(dateTime, errorMessages) {
        this.REGEX_FORMAT = /\[([^\]]+)]|y{1,4}|M{1,4}|d{1,4}|H{1,2}|h{1,2}|t|T|m{1,2}|s{1,2}|Z{1,2}/g;
        // noinspection SpellCheckingInspection
        this.englishFormats = {
            LTS: 'h:mm:ss T',
            LT: 'h:mm T',
            L: 'MM/dd/yyyy',
            LL: 'MMMM d, yyyy',
            LLL: 'MMMM d, yyyy h:mm T',
            LLLL: 'dddd, MMMM d, yyyy h:mm T',
        };
        this.formattingTokens = /(\[[^[]*])|([-_:/.,()\s]+)|(T|t|yyyy|yy?|MM?M?M?|Do|dd?|hh?|HH?|mm?|ss?|z|zz?z?)/g;
        this.match1 = /\d/; // 0 - 9
        this.match2 = /\d\d/; // 00 - 99
        this.match3 = /\d{3}/; // 000 - 999
        this.match4 = /\d{4}/; // 0000 - 9999
        this.match1to2 = /\d\d?/; // 0 - 99
        this.matchSigned = /[+-]?\d+/; // -inf - inf
        this.matchOffset = /[+-]\d\d:?(\d\d)?|Z/; // +00:00 -00:00 +0000 or -0000 +00 or Z
        this.matchWord = /\d*[^-_:/,()\s\d]+/; // Word
        this.zoneExpressions = [
            this.matchOffset,
            (obj, input) => {
                obj.offset = this.offsetFromString(input);
            },
        ];
        this.expressions = {
            t: [
                this.matchWord,
                (ojb, input) => {
                    ojb.afternoon = this.meridiemMatch(input);
                },
            ],
            T: [
                this.matchWord,
                (ojb, input) => {
                    ojb.afternoon = this.meridiemMatch(input);
                },
            ],
            fff: [
                this.match3,
                (ojb, input) => {
                    ojb.milliseconds = +input;
                },
            ],
            s: [this.match1to2, this.addInput('seconds')],
            ss: [this.match1to2, this.addInput('seconds')],
            m: [this.match1to2, this.addInput('minutes')],
            mm: [this.match1to2, this.addInput('minutes')],
            H: [this.match1to2, this.addInput('hours')],
            h: [this.match1to2, this.addInput('hours')],
            HH: [this.match1to2, this.addInput('hours')],
            hh: [this.match1to2, this.addInput('hours')],
            d: [this.match1to2, this.addInput('day')],
            dd: [this.match2, this.addInput('day')],
            Do: [
                this.matchWord,
                (ojb, input) => {
                    [ojb.day] = input.match(/\d+/);
                    if (!this.localization.ordinal)
                        return;
                    for (let i = 1; i <= 31; i += 1) {
                        if (this.localization.ordinal(i).replace(/[[\]]/g, '') === input) {
                            ojb.day = i;
                        }
                    }
                },
            ],
            M: [this.match1to2, this.addInput('month')],
            MM: [this.match2, this.addInput('month')],
            MMM: [
                this.matchWord,
                (obj, input) => {
                    const months = this.getAllMonths();
                    const monthsShort = this.getAllMonths('short');
                    const matchIndex = (monthsShort || months.map((_) => _.slice(0, 3))).indexOf(input) + 1;
                    if (matchIndex < 1) {
                        throw new Error();
                    }
                    obj.month = matchIndex % 12 || matchIndex;
                },
            ],
            MMMM: [
                this.matchWord,
                (obj, input) => {
                    const months = this.getAllMonths();
                    const matchIndex = months.indexOf(input) + 1;
                    if (matchIndex < 1) {
                        throw new Error();
                    }
                    obj.month = matchIndex % 12 || matchIndex;
                },
            ],
            y: [this.matchSigned, this.addInput('year')],
            yy: [
                this.match2,
                (obj, input) => {
                    obj.year = this.parseTwoDigitYear(input);
                },
            ],
            yyyy: [this.match4, this.addInput('year')],
            // z: this.zoneExpressions,
            // zz: this.zoneExpressions,
            // zzz: this.zoneExpressions
        };
        this.parseFormattedInput = (input) => {
            if (!this.localization.format) {
                this.errorMessages.customDateFormatError('No format was provided');
            }
            try {
                if (['x', 'X'].indexOf(this.localization.format) > -1)
                    return new this.DateTime((this.localization.format === 'X' ? 1000 : 1) * input);
                const parser = this.makeParser(this.localization.format);
                const { year, month, day, hours, minutes, seconds, milliseconds, zone } = parser(input);
                const now = new this.DateTime();
                const d = day || (!year && !month ? now.getDate() : 1);
                const y = year || now.getFullYear();
                let M = 0;
                if (!(year && !month)) {
                    M = month > 0 ? month - 1 : now.getMonth();
                }
                const h = hours || 0;
                const m = minutes || 0;
                const s = seconds || 0;
                const ms = milliseconds || 0;
                if (zone) {
                    return new this.DateTime(Date.UTC(y, M, d, h, m, s, ms + zone.offset * 60 * 1000));
                }
                return new this.DateTime(y, M, d, h, m, s, ms);
            }
            catch (e) {
                this.errorMessages.customDateFormatError(`Unable to parse provided input: ${input}, format: ${this.localization.format}`);
                return new this.DateTime(''); // Invalid Date
            }
        };
        this.DateTime = dateTime;
        this.errorMessages = errorMessages;
    }
    getAllMonths(format = 'long') {
        const applyFormat = new Intl.DateTimeFormat(this.localization.locale, {
            month: format,
        }).format;
        return [...Array(12).keys()].map((m) => applyFormat(new Date(2021, m)));
    }
    replaceTokens(formatStr, formats) {
        return formatStr.replace(/(\[[^\]]+])|(LTS?|l{1,4}|L{1,4})/g, (_, a, b) => {
            const B = b && b.toUpperCase();
            return a || formats[B] || this.englishFormats[B];
        });
    }
    parseTwoDigitYear(input) {
        input = +input;
        return input + (input > 68 ? 1900 : 2000);
    }
    offsetFromString(string) {
        if (!string)
            return 0;
        if (string === 'Z')
            return 0;
        const parts = string.match(/([+-]|\d\d)/g);
        const minutes = +(parts[1] * 60) + (+parts[2] || 0);
        return minutes === 0 ? 0 : parts[0] === '+' ? -minutes : minutes; // eslint-disable-line no-nested-ternary
    }
    addInput(property) {
        return (time, input) => {
            time[property] = +input;
        };
    }
    /**
     * z = -4, zz = -04, zzz = -0400
     * @param date
     * @param style
     * @private
     */
    zoneInformation(date, style) {
        let name = date
            .parts(this.localization.locale, { timeZoneName: 'longOffset' })
            .timeZoneName.replace('GMT', '')
            .replace(':', '');
        const negative = name.includes('-');
        name = name.replace('-', '');
        if (style === 'z')
            name = name.substring(1, 2);
        else if (style === 'zz')
            name = name.substring(0, 2);
        return `${negative ? '-' : ''}${name}`;
    }
    meridiemMatch(input) {
        const meridiem = new Intl.DateTimeFormat(this.localization.locale, {
            hour: 'numeric',
            hour12: true,
        })
            .formatToParts(new Date(2022, 3, 4, 13))
            .find((p) => p.type === 'dayPeriod')?.value;
        return input.toLowerCase() === meridiem.toLowerCase();
    }
    correctHours(time) {
        const { afternoon } = time;
        if (afternoon !== undefined) {
            const { hours } = time;
            if (afternoon) {
                if (hours < 12) {
                    time.hours += 12;
                }
            }
            else if (hours === 12) {
                time.hours = 0;
            }
            delete time.afternoon;
        }
    }
    makeParser(format) {
        format = this.replaceTokens(format, this.localization.dateFormats);
        const array = format.match(this.formattingTokens);
        const { length } = array;
        for (let i = 0; i < length; i += 1) {
            const token = array[i];
            const parseTo = this.expressions[token];
            const regex = parseTo && parseTo[0];
            const parser = parseTo && parseTo[1];
            if (parser) {
                array[i] = { regex, parser };
            }
            else {
                array[i] = token.replace(/^\[|]$/g, '');
            }
        }
        return (input) => {
            const time = {};
            for (let i = 0, start = 0; i < length; i += 1) {
                const token = array[i];
                if (typeof token === 'string') {
                    start += token.length;
                }
                else {
                    const { regex, parser } = token;
                    const part = input.slice(start);
                    const match = regex.exec(part);
                    const value = match[0];
                    parser.call(this, time, value);
                    input = input.replace(value, '');
                }
            }
            this.correctHours(time);
            return time;
        };
    }
    format(dateTime) {
        if (!dateTime)
            return dateTime;
        if (JSON.stringify(dateTime) === 'null')
            return 'Invalid Date';
        const format = this.replaceTokens(this.localization.format ||
            `${this.englishFormats.L}, ${this.englishFormats.LT}`, this.localization.dateFormats);
        const formatter = (template) => new Intl.DateTimeFormat(this.localization.locale, template).format(dateTime);
        //if the format asks for a twenty-four-hour string but the hour cycle is not, then make a base guess
        const HHCycle = this.localization.hourCycle.startsWith('h1')
            ? 'h24'
            : this.localization.hourCycle;
        const hhCycle = this.localization.hourCycle.startsWith('h2')
            ? 'h12'
            : this.localization.hourCycle;
        const matches = {
            yy: formatter({ year: '2-digit' }),
            yyyy: dateTime.year,
            M: formatter({ month: 'numeric' }),
            MM: dateTime.monthFormatted,
            MMM: this.getAllMonths('short')[dateTime.getMonth()],
            MMMM: this.getAllMonths()[dateTime.getMonth()],
            d: dateTime.date,
            dd: dateTime.dateFormatted,
            ddd: formatter({ weekday: 'short' }),
            dddd: formatter({ weekday: 'long' }),
            H: dateTime.getHours(),
            HH: dateTime.getHoursFormatted(HHCycle),
            h: dateTime.hours > 12 ? dateTime.hours - 12 : dateTime.hours,
            hh: dateTime.getHoursFormatted(hhCycle),
            t: dateTime.meridiem(),
            T: dateTime.meridiem().toUpperCase(),
            m: dateTime.minutes,
            mm: dateTime.minutesFormatted,
            s: dateTime.seconds,
            ss: dateTime.secondsFormatted,
            fff: dateTime.getMilliseconds(),
            // z: this.zoneInformation(dateTime, 'z'), //-4
            // zz: this.zoneInformation(dateTime, 'zz'), //-04
            // zzz: this.zoneInformation(dateTime, 'zzz') //-0400
        };
        return format.replace(this.REGEX_FORMAT, (match, $1) => {
            return $1 || matches[match];
        });
    }
}
var index = (_, tdClasses) => {
    const customDateFormat = new CustomDateFormat(tdClasses.DateTime, tdClasses.Namespace.errorMessages);
    // noinspection JSUnusedGlobalSymbols
    tdClasses.Dates.prototype.formatInput = function (date) {
        if (!date)
            return '';
        customDateFormat.localization = this.optionsStore.options.localization;
        return customDateFormat.format(date);
    };
    // noinspection JSUnusedGlobalSymbols
    tdClasses.Dates.prototype.parseInput = function (input) {
        customDateFormat.localization = this.optionsStore.options.localization;
        return customDateFormat.parseFormattedInput(input);
    };
    tdClasses.DateTime.fromString = function (input, localization) {
        customDateFormat.localization = localization;
        return customDateFormat.parseFormattedInput(input);
    };
};return index;}));