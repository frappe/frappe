import { Calendar as FullCalendar } from "@fullcalendar/core";
import dayGridPlugin from "@fullcalendar/daygrid";
import listPlugin from "@fullcalendar/list";
import timeGridPlugin from "@fullcalendar/timegrid";
import interactionPlugin from "@fullcalendar/interaction";
import allLocales from "@fullcalendar/core/locales-all";

frappe.FullCalendar = FullCalendar;
frappe.FullCalendar.Plugins = [listPlugin, dayGridPlugin, timeGridPlugin, interactionPlugin];
// The view passes `locale: frappe.boot.lang`, but FullCalendar can only honour a
// locale it has been given. Without this the option is accepted and ignored, and
// every calendar renders its month names, day names and buttons in English.
frappe.FullCalendar.Locales = allLocales;
