import ar from "air-datepicker/locale/ar";
import bg from "air-datepicker/locale/bg";
import ca from "air-datepicker/locale/ca";
import cs from "air-datepicker/locale/cs";
import da from "air-datepicker/locale/da";
import de from "air-datepicker/locale/de";
import el from "air-datepicker/locale/el";
import en from "air-datepicker/locale/en";
import es from "air-datepicker/locale/es";
import eu from "air-datepicker/locale/eu";
import fi from "air-datepicker/locale/fi";
import fr from "air-datepicker/locale/fr";
import hr from "air-datepicker/locale/hr";
import hu from "air-datepicker/locale/hu";
import id from "air-datepicker/locale/id";
import it from "air-datepicker/locale/it";
import ja from "air-datepicker/locale/ja";
import ko from "air-datepicker/locale/ko";
import nb from "air-datepicker/locale/nb";
import nl from "air-datepicker/locale/nl";
import pl from "air-datepicker/locale/pl";
import pt from "air-datepicker/locale/pt";
import pt_BR from "air-datepicker/locale/pt-BR";
import ro from "air-datepicker/locale/ro";
import ru from "air-datepicker/locale/ru";
import si from "air-datepicker/locale/si";
import sk from "air-datepicker/locale/sk";
import sl from "air-datepicker/locale/sl";
import sv from "air-datepicker/locale/sv";
import th from "air-datepicker/locale/th";
import tr from "air-datepicker/locale/tr";
import uk from "air-datepicker/locale/uk";
import zh from "air-datepicker/locale/zh";

const locales = {
	ar,
	bg,
	ca,
	cs,
	da,
	de,
	el,
	en,
	es,
	eu,
	fi,
	fr,
	hr,
	hu,
	id,
	it,
	ja,
	ko,
	nb,
	nl,
	pl,
	pt,
	"pt-BR": pt_BR,
	ro,
	ru,
	si,
	sk,
	sl,
	sv,
	th,
	tr,
	uk,
	zh,
	bs: {
		days: ["Nedjelja", "Ponedjeljak", "Utorak", "Srijeda", "Četvrtak", "Petak", "Subota"],
		daysShort: ["Ned", "Pon", "Uto", "Sri", "Čet", "Pet", "Sub"],
		daysMin: ["Ne", "Po", "Ut", "Sr", "Če", "Pe", "Su"],
		months: [
			"Januar",
			"Februar",
			"Mart",
			"April",
			"Maj",
			"Juni",
			"Juli",
			"August",
			"Septembar",
			"Oktobar",
			"Novembar",
			"Decembar",
		],
		monthsShort: [
			"Jan",
			"Feb",
			"Mar",
			"Apr",
			"Maj",
			"Jun",
			"Jul",
			"Aug",
			"Sep",
			"Okt",
			"Nov",
			"Dec",
		],
		today: "Danas",
		clear: "Resetiraj",
		dateFormat: "dd/MM/yyyy",
		timeFormat: "HH:mm",
		firstDay: 1,
	},
	sr: {
		days: ["Недеља", "Понедељак", "Уторак", "Среда", "Четвртак", "Петак", "Субота"],
		daysShort: ["Нед", "Пон", "Уто", "Сре", "Чет", "Пет", "Суб"],
		daysMin: ["Не", "По", "Ут", "Ср", "Че", "Пе", "Су"],
		months: [
			"Јануар",
			"Фебруар",
			"Март",
			"Април",
			"Мај",
			"Јун",
			"Јул",
			"Август",
			"Септембар",
			"Октобар",
			"Новембар",
			"Децембар",
		],
		monthsShort: [
			"Јан",
			"Феб",
			"Мар",
			"Апр",
			"Мај",
			"Јун",
			"Јул",
			"Авг",
			"Сеп",
			"Окт",
			"Нов",
			"Дец",
		],
		today: "Данас",
		clear: "Ресетуј",
		dateFormat: "dd/MM/yyyy",
		timeFormat: "HH:mm",
		firstDay: 1,
	},
	"sr-CS": {
		days: ["Nedelja", "Ponedeljak", "Utorak", "Sreda", "Četvrtak", "Petak", "Subota"],
		daysShort: ["Ned", "Pon", "Uto", "Sre", "Čet", "Pet", "Sub"],
		daysMin: ["Ne", "Po", "Ut", "Sr", "Če", "Pe", "Su"],
		months: [
			"Januar",
			"Februar",
			"Mart",
			"April",
			"Maj",
			"Jun",
			"Jul",
			"Avgust",
			"Septembar",
			"Oktobar",
			"Novembar",
			"Decembar",
		],
		monthsShort: [
			"Jan",
			"Feb",
			"Mar",
			"Apr",
			"Maj",
			"Jun",
			"Jul",
			"Avg",
			"Sep",
			"Okt",
			"Nov",
			"Dec",
		],
		today: "Danas",
		clear: "Resetuj",
		dateFormat: "dd/MM/yyyy",
		timeFormat: "HH:mm",
		firstDay: 1,
	},
};

frappe.ui.form.get_datepicker_locale = (lang) => {
	lang = lang || frappe.boot?.user?.language || "en";
	return locales[lang] || locales[lang.split("-")[0]] || locales.en;
};
