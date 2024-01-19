// website_script.js
{% if javascript -%}{{ javascript }}{%- endif %}

{% if google_analytics_id -%}
// Google Analytics
(function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
(i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
})(window,document,'script','//www.google-analytics.com/analytics.js','ga');

ga('create', '{{ google_analytics_id }}', 'auto');
{% if google_analytics_anonymize_ip %}
ga('set', 'anonymizeIp', true);
{% endif %}
ga('send', 'pageview');
// End Google Analytics
{%- endif %}

{% if enable_view_tracking %}

	window.frappe.track = (event_name) => { // TODO: add similar, optimized utility to frappe/builder
    		if (navigator.doNotTrack != 1) {document.addEventListener("DOMContentLoaded", function() {let b=getBrowser(),q=getQueryParams(),c=getCookies(),m=getMetaTags();import('https://openfpcdn.io/fingerprintjs/v3').then(f=>f.load()).then(fp=>fp.get()).then(r=>{const d={event_name:event_name,referrer:document.referrer,browser:b.name,version:b.version,user_tz:Intl.DateTimeFormat().resolvedOptions().timeZone,source:q.source,medium:q.medium,campaign:q.campaign,visitor_id:r.visitorId{%- if tracking_data_capture_js -%},data:function() {{{ tracking_data_capture_js }};return r}{%- endif -%}};makeViewLog(d)})})}function getBrowser(){const ua=navigator.userAgent,b={};if(ua.indexOf("Chrome")!==-1){b.name="Chrome";b.version=parseInt(ua.split("Chrome/")[1])}else if(ua.indexOf("Firefox")!==-1){b.name="Firefox";b.version=parseInt(ua.split("Firefox/")[1])}else{b.name="Unknown";b.version="Unknown"}return b}function getQueryParams(){const q={},p=window.location.search.substring(1).split("&");p.forEach(p=>{const [k,v]=p.split("=");q[k]=v});return q}function getCookies(){const c={},ee=document.cookie.search.substring(1).split(";");ee.forEach(e=>{const [k,v]=e.split("=");c[k]=v});return c}function getMetaTags(){const m={},tt=document.getElementsByTagName('meta');tt.forEach(t=>{const [k,v]=((t.getAttribute('name')||t.getAttribute('property')||t.getAttribute('http-equiv')),t.getAttribute('content'));m[k]=v});return m}function makeViewLog(d){fetch('/api/method/frappe.website.log_event',{method:'POST',headers:{'Content-Type':'application/json',"X-Frappe-CSRF-Token": frappe.csrf_token},body:JSON.stringify(d)})}
	};

	frappe.track("WebPageView"));

{% endif %}
