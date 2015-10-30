Standard Print formats are <b>auto generated</b> from the layout of the DocType. You can customize the standard format by
<br>
<br>

<h4>1. Customizing Standard Print</h4>
Go to <b>Setup &gt; Customize &gt; Customize Form View </b>and you can:
<br>
<ol>
    <li>Re-arranging fields by dragging and dropping</li>
    <li>Add static elements by adding <b>HTML</b> type fields and adding your HTML in <b>Options</b>

    </li>
    <li>Hiding fields by setting the <b>Print Hide</b> property</li>
</ol>
<hr>

<h4>2. Creating new layouts based on Print Formats</h4>

<p>As there are not templates that are generated for standard Print Formats, you will have to create new templates from scratch using the <a href="http://jinja.pocoo.org/" target="_blank">Jinja Templating Language</a> via</p>
<p><b>Setup &gt; Printing and Branding &gt; Print Format</b>

</p>
<ol>
    <li><a href="https://erpnext.com/user-guide/customize-erpnext/print-format" target="_blank">See Print Format help</a>.
        <br>
    </li>
    <li>You can use the <a href="http://getbootstrap.com" target="_blank">Bootstrap CSS framework</a> to layout your print formats
        <br>
    </li>
</ol>
<hr>
<p><b>Tip: You can import <a href="https://github.com/frappe/frappe/blob/develop/frappe/templates/print_formats/standard_macros.html" target="_blank">Standard Template macros</a> for building your print formats.</b>

</p>
<p>Example, adding the standard header:
    <br>
</p>
<pre><code>{% raw %}{%- from "templates/print_formats/standard_macros.html" import add_header -%}
{{ add_header() }}{% endraw %}
</code></pre>
