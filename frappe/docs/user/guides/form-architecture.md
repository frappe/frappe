<style>
    td { 
    padding:5px 10px 5px 5px;
    };
    img {
    align:center;
    };
table, th, td {
    border: 1px solid black;
    border-collapse: collapse;
}
</style>
ERPNext is built on top of framework called **Frappe**. In this framework, each form is created as a table called 'Doctype'. Each Doctype has fields listed as a row, with properties define for them assigned like [field type](https://erpnext.com/kb/setup/field-types), print show/hide, Mandatory etc.

For an instance, Sales order is a table, in which sales order fields are defined as a rows.

Doctype - Sales Order

<table border="1px">
<tbody>
<tr align="center">
  <td><b>Field ID</b></td>
  <td><b>Field Type</b></td>
  <td><b>Print Hide</b></td>
  <td><b>Mandatory</b></td>
  <td><b>Hidden</b></td>
</tr>
<tr>
  <td>Series</td>
  <td>Select</td>
  <td>1 (checked)</td>
  <td>1 </td>
  <td>0 (unchecked)</td>
</tr>
<tr>
  <td>Customer</td>
  <td>Link</td>
  <td>0 </td>
  <td>1 </td>
  <td>0 </td>
</tr>
<tr>
  <td>Item</td>
  <td>Table</td>
  <td>0 </td>
  <td>1 </td>
  <td>0 </td>
</tr>
</tbody>
</table>
<br>
To capture more details of sales order, like item detail, separate table is created called "Sales Order Item" table. Likewise, taxes are the separate table in a Sales Order. So, for Sales Order form, Sales Order Doctype becomes parent, and Sales Order Item and Sales Taxes Charges and Sales Person Docytpe becomes child table.

Following is the Doctype structure for few important transaction of ERPNext.

<table border="1">
<tbody>
<tr>
  <td style="text-align: center;"><b>Transaction</b></td>
  <td style="text-align: center;"><b>Table</b></td>
  <td style="text-align: center;"><b>Doctype Name</b></td> 
</tr>
<tr>
  <td>Quotation </td>
  <td>Quotation</td>
  <td>Quotation</td>
</tr>
<tr>
  <td><br /></td>
  <td>Quotation Item table</td>
  <td>Quotation Item</td>
</tr>
<tr>
  <td><br /></td>
  <td>Quotation Taxes</td>
  <td>Sales Taxes and Charges</td>
</tr>
<tr>
  <td>Sales Order</td>
  <td>Sales Order</td>
  <td>Sales Order</td>
</tr>
<tr>
  <td><br /></td>
  <td>Sales Order Item table</td>
  <td>Sales Order Item </td>
</tr>
<tr>
  <td><br /></td>
  <td>Sales Order Taxes</td>
  <td>Sales Taxes and Charges</td>
</tr>
<tr>
  <td>Delivery Note</td>
  <td>Delivery note</td>
  <td>Delivery Note</td>
</tr>
<tr>
  <td><br /></td>
  <td>Delivery Note Item table</td>
  <td>Delivery Note Item</td>
</tr>
<tr>
  <td><br /></td>
  <td>Delivery Note Taxes</td>
  <td>Sales Taxes and Charges</td>
</tr>
<tr>
  <td>Sales Invoice</td>
  <td>sales invoice</td>
  <td>Sales Invoice</td>
</tr>
<tr>
  <td></td>
  <td>Sales Invoice Item table</td>
  <td>Sales Invoice Item</td>
</tr>
<tr>
  <td></td>
  <td>Sales Invoice Tax table</td>
  <td>Sales Taxes and Charges</td>
</tr>
<tr>
  <td>Purchase Order</td>
  <td>Purchase Order</td>
  <td>Purchase Order</td>
</tr>
<tr>
  <td></td>
  <td>Purchase Order Item table</td>
  <td>Purchase Order Item</td>
</tr>
<tr>
  <td>Purchase Receipt</td>
  <td>Purchase Receipt</td>
  <td>Purchase Receipt</td>
</tr>
<tr>
  <td></td>
  <td>Purchase Receipt Item table</td>
  <td>Purchase Receipt Item</td>
</tr>
<tr>
  <td>Purchase Invoice</td>
  <td>Purchase Invoice</td>
  <td>Purchase Invoice </td>
</tr>
<tr>
  <td></td>
  <td>Purchase Invoice Item table</td>
  <td>Purchase Invoice Item</td>
</tr>
<tr>
  <td></td>
  <td>Purchase Invoice Tax table</td>
  <td>Purchase Taxes and Charges</td>
</tr>
<tr>
  <td>Journal Voucher</td>
  <td>Journal Voucher</td>
  <td>Journal Voucher</td>
</tr>
<tr>
  <td></td>
  <td>Journal Voucher Accounts table</td>
  <td>Journal Voucher Detail</td>
</tr>
</tbody>
</table>

<!-- markdown -->