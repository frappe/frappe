frappe.provide('frappe.desktop');

redirect_url = localStorage.redirect_to
localStorage.removeItem('redirect_to')
if(redirect_url){
    window.location.href = redirect_url
}
