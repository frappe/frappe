{% if javascript -%}{{ javascript }}{%- endif %}

{% if google_analytics_id -%}
// Google Analytics template
window._gaq = window._gaq || [];
window._gaq.push(['_setAccount', '{{ google_analytics_id }}']);
window._gaq.push(['_trackPageview']);

(function() {
    var ga = document.createElement('script'); ga.type = 'text/javascript'; ga.async = true;
    ga.src = ('https:' == document.location.protocol ? 'https://ssl' : 'http://www') + '.google-analytics.com/ga.js';
    var s = document.getElementsByTagName('script')[0]; s.parentNode.insertBefore(ga, s);
})();
{%- endif %}