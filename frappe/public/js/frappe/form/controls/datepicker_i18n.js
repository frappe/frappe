import en from "air-datepicker/locale/en";

const locales = { en };
const intl_languages = { "sr-CS": "sr-Latn" };

function make_locale(lang) {
	const format = (options, date) =>
		new Intl.DateTimeFormat(intl_languages[lang] || lang, {
			timeZone: "UTC",
			calendar: "gregory",
			...options,
		}).format(date);
	const days = (options) =>
		Array.from({ length: 7 }, (_, i) => format(options, new Date(Date.UTC(2023, 0, 1 + i))));
	const months = (options) =>
		Array.from({ length: 12 }, (_, i) => format(options, new Date(Date.UTC(2023, i, 1))));
	const days_short = days({ weekday: "short" });

	return {
		...en,
		days: days({ weekday: "long" }),
		daysShort: days_short,
		daysMin: days_short.map((day) => day.replace(/\.$/, "")),
		months: months({ month: "long" }),
		monthsShort: months({ month: "short" }),
	};
}

frappe.ui.form.get_datepicker_locale = (lang) => {
	lang = lang || frappe.boot?.user?.language || "en";
	if (!locales[lang]) {
		try {
			locales[lang] = make_locale(lang);
		} catch {
			locales[lang] = en;
		}
	}
	return locales[lang];
};
