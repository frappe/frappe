Let's say, there is a custom field "VAT Number" in Supplier master, which should be fetched in Purchase Order document.
<br>
<br>Steps:
<br>1. Create a Custom Field <b>"VAT Number"</b> for <b>Supplier</b> document with <b>Field Type</b> as <b>Data</b>.
<br>&nbsp;&nbsp;
<img src="/files/supplier_vat_number.png" height="202" width="607"><br>2. Create another Custom Field <b>"VAT Number"</b> for Purchase Order document. But in this case, enter <b>Field Type</b> as <b>Read Only</b> and <b>Options</b> as <b>supplier.vat_number</b>.
<br>&nbsp; <img src="/files/po_vat_number.png" height="264" width="611"><br>3. Refresh the system using <b>Help -&gt; Clear Cache</b>.
<br>4. Now on selection of Supplier in new Purchase Order form, "VAT Number" will be fetched automatically from Supplier master.
<br>5. The above procedure should be replicated, for all other supplier related transactions.
<br>
<br>Note:
<br>
<blockquote>If field type of "VAT Number" in Purchase Order is other than `Read Only`, then to fetch the value, a small piece of Custom Script need to be written.
    <br>i. Go to Setup -&gt; Customize -&gt; Custom Script.
    <br>ii. Select DocType as `Purchase Order`.
    <br>iii. Add Script `cur_frm.add_fetch('supplier', 'vat_number', 'vat_number')`
    <br>iv. Save the Custom Script.
    <br>v. Clear cache before testing.
    <br>
</blockquote>