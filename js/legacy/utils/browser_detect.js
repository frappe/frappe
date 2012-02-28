// Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
// 
// MIT License (MIT)
// 
// Permission is hereby granted, free of charge, to any person obtaining a 
// copy of this software and associated documentation files (the "Software"), 
// to deal in the Software without restriction, including without limitation 
// the rights to use, copy, modify, merge, publish, distribute, sublicense, 
// and/or sell copies of the Software, and to permit persons to whom the 
// Software is furnished to do so, subject to the following conditions:
// 
// The above copyright notice and this permission notice shall be included in 
// all copies or substantial portions of the Software.
// 
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
// INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
// PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
// HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
// CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
// OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
// 

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