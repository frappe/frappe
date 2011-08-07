/* Version Detect */

var appVer = navigator.appVersion.toLowerCase();
var is_minor = parseFloat(appVer);
var is_major = parseInt(is_minor);
var iePos = appVer.indexOf('msie');
if (iePos !=-1) {
	is_minor = parseFloat(appVer.substring(iePos+5,appVer.indexOf(';',iePos)))
	is_major = parseInt(is_minor);
}
var isIE = (iePos!=-1);
var isIE6 = (isIE && is_major <= 6);
var isIE7 = (isIE && is_major >= 7);
if (/Firefox[\/\s](\d+\.\d+)/.test(navigator.userAgent)){ //test for Firefox/x.x or Firefox x.x (ignoring remaining digits);
	var isFF = 1;
	var ffversion=new Number(RegExp.$1) // capture x.x portion and store as a number
	if (ffversion>=3) var isFF3 = 1;
	else if (ffversion>=2) var isFF2 = 1;
	else if (ffversion>=1) var isFF1 = 1;
}
var isSafari = navigator.userAgent.indexOf('Safari')!=-1 ? 1 : 0;
var isChrome = navigator.userAgent.indexOf('Chrome')!=-1 ? 1 : 0;