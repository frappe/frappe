/*!
  * Tempus Dominus v6.2.10 (https://getdatepicker.com/)
  * Copyright 2013-2022 Jonathan Peterson
  * Licensed under MIT (https://github.com/Eonasdan/tempus-dominus/blob/master/LICENSE)
  */
(function(g,f){typeof exports==='object'&&typeof module!=='undefined'?f(exports):typeof define==='function'&&define.amd?define(['exports'],f):(g=typeof globalThis!=='undefined'?globalThis:g||self,f((g.tempusDominus=g.tempusDominus||{},g.tempusDominus.plugins=g.tempusDominus.plugins||{},g.tempusDominus.plugins.fa_five={})));})(this,(function(exports){'use strict';// this obviously requires the FA 6 libraries to be loaded
const faFiveIcons = {
    type: 'icons',
    time: 'fas fa-clock',
    date: 'fas fa-calendar',
    up: 'fas fa-arrow-up',
    down: 'fas fa-arrow-down',
    previous: 'fas fa-chevron-left',
    next: 'fas fa-chevron-right',
    today: 'fas fa-calendar-check',
    clear: 'fas fa-trash',
    close: 'fas fa-times',
};
// noinspection JSUnusedGlobalSymbols
const load = (_, __, tdFactory) => {
    tdFactory.DefaultOptions.display.icons = faFiveIcons;
};exports.faFiveIcons=faFiveIcons;exports.load=load;Object.defineProperty(exports,'__esModule',{value:true});}));