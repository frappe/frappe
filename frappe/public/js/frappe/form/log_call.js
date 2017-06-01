frappe.ui.form.on("Lead", "refresh", function(frm) {
    var promptInfo = [
      {label: "Contact", fieldtype: "Select", options: frm.doc.lead_name,
      default:frm.doc.lead_name, read_only: "1"},
      {fieldtype: "Column Break"},
      {label: "Phone", fieldname: "phone_no", fieldtype: "Data",
      options: [frm.doc.phone, frm.doc.mobile_no], default: frm.doc.phone, read_only: "1"},
      {fieldtype: "Section Break"},
      {label: "Sent or Received", fieldname: "sent_or_received",
      fieldtype: "Select", options: ["Sent", "Received"], default: "Sent"},
      {fieldtype: "Column Break"},
      {label: "Next Contact Date", fieldtype: "Date", reqd: "1"},
      {fieldtype: "Section Break"},
      {label: "Subject", fieldtype: "Data", default: "Call " + (new Date())},
      {fieldtype: "Section Break"},
      {label: "Notes", fieldname: "content", fieldtype: "Small Text", reqd: "1"}
    ]
    frm.add_custom_button(__("Log Call"), function(foo) {
      frappe.call({
        method: "frappe.client.get_list",
        args: {
          "doctype": "Communication",
          "fields": ["Subject", "Content", "Communication_Date", "Communication_Type"],
          "filters": {
            "reference_doctype": frm.doc.doctype,
            "reference_name": frm.doc.name,
            "communication_type": ["in", ["Comment", "Communication"]]
          }
        },
        callback: function(r) {
          promptInfo.push({fieldtype: "Section Break"})
          if(r.message != undefined) {
            r.message.forEach(function(messageData) {
              var content = ""
              if(messageData.Communication_Type == "Comment") {
                if(messageData.Content != null && messageData.Subject != null && messageData.Content < messageData.Subject) {
                  content = messageData.Subject + '\n' + messageData.Content
                } else if(messageData.Content != null) {
                  content = messageData.Content
                } else if (foo.Subject != null) {
                  content = messageData.Subject
                }
                newMessage = {label: "<i class='octicon octicon-comment-discussion icon-fixed-width'></i>Comment - " + messageData.Communication_Date, fieldname: "message",
                              fieldtype: "Small Text", default: content, read_only: "1"}
              } else if (foo.Communication_Type == "Communication") {
                content = messageData.Subject + '\n' + messageData.Content
                newMessage = {label: "<i class='octicon octicon-device-mobile icon-fixed-width'></i> Communication", fieldname: "message",
                              fieldtype: "Small Text", default: content, read_only: "1"}
              }
              var state = true
              promptInfo.forEach(function(bar) {
                if(JSON.stringify(bar) == JSON.stringify(newMessage)) {
                  state = false
                }
              })
              if(state) {
                promptInfo.push(newMessage);
                promptInfo.push({fieldtype: "Section Break"});
              }''
            })
          }
          var communication = frappe.prompt(promptInfo,
            function(data){
              frm.doc.contact_date = data.next_contact_date;
              frm.doc.contact_by = frappe.user.name;
              frappe.call({
                method: "erpnext_controllers.erpnext_controllers.methods.log_call.update_doc",
                args: {
                  "doc": frm.doc
                },
                callback: function(r) {
                  frappe.call({
                    method: "erpnext_controllers.erpnext_controllers.methods.log_call.make_communication",
                    args: {
                      "doc": frm.doc,
                      "communication": data
                    },
                    callback: function(r){
                      cur_frm.refresh();
                    }
                  })
                }
              })
            });
          }
        });
    });
});

frappe.ui.form.on("Opportunity", "refresh", function(frm) {
    var promptInfo = [
        {label: "Contact", fieldtype: "Select", options: frm.doc.customer_name,
        default:frm.doc.customer_name},
        {fieldtype: "Column Break"},
        {label: "Phone", fieldname: "phone_no", fieldtype: "Select",
        options: [frm.doc.phone, frm.doc.contact_mobile], default: frm.doc.contact_mobile},
        {fieldtype: "Section Break"},
        {label: "Sent or Received", fieldname: "sent_or_received",
        fieldtype: "Select", options: ["Sent", "Received"], default: "Sent"},
        {fieldtype: "Column Break"},
        {label: "Next Contact Date", fieldtype: "Date", reqd: "1"},
        {fieldtype: "Section Break"},
        {label: "Subject", fieldtype: "Data", default: "Call " + (new Date())},
        {fieldtype: "Section Break"},
        {label: "Notes", fieldname: "content", fieldtype: "Small Text", reqd:"1"}
      ]
    frm.add_custom_button(__("Log Call"), function(foo) {
      frappe.call({
        method: "frappe.client.get_list",
        args: {
          "doctype": "Communication",
          "fields": ["Subject", "Content", "Communication_Date", "Communication_Type"],
          "filters": {
            "reference_doctype": frm.doc.doctype,
            "reference_name": frm.doc.name,
            "communication_type": ["in", ["Comment", "Communication"]]
          }
        },
        callback: function(r) {
          promptInfo.push({fieldtype: "Section Break"})
          if(r.message != undefined) {
            r.message.forEach(function(messageData) {
              var content = ""
              if(messageData.Communication_Type == "Comment") {
                if(messageData.Content != null && messageData.Subject != null && messageData.Content < messageData.Subject) {
                  content = messageData.Subject + '\n' + messageData.Content
                } else if(messageData.Content != null) {
                  content = messageData.Content
                } else if (messageData.Subject != null) {
                  content = messageData.Subject
                }
                newMessage = {label: "<i class='octicon octicon-comment-discussion icon-fixed-width'></i>Comment - " + messageData.Communication_Date, fieldname: "message",
                              fieldtype: "Small Text", default: content, read_only: "1"}
              } else if (foo.Communication_Type == "Communication") {
                content = messageData.Subject + '\n' + messageData.Content
                newMessage = {label: "<i class='octicon octicon-device-mobile icon-fixed-width'></i> Communication", fieldname: "message",
                              fieldtype: "Small Text", default: content, read_only: "1"}
              }
              var state = true
              promptInfo.forEach(function(promptMessage) {
                if(JSON.stringify(promptMessage) == JSON.stringify(newMessage)) {
                  state = false
                }
              })
              if (state) {
                promptInfo.push(newMessage)
                promptInfo.push({fieldtype: "Section Break"})
              }
            })
          }
          var communication = frappe.prompt(promptInfo,
            function(data) {
              frm.doc.contact_date = data.next_contact_date;
              frm.doc.contact_by = frappe.user.name;
              frappe.call({
                method: "erpnext_controllers.erpnext_controllers.methods.log_call.update_doc",
                args: {
                  "doc": frm.doc
                },
                callback: function(r) {
                  frappe.call({
                    method: "erpnext_controllers.erpnext_controllers.methods.log_call.make_communication",
                    args: {
                      "doc": frm.doc,
                      "communication": data
                    },
                    callback: function(r) {
                      cur_frm.refresh();
                    }
                  })
                }
              })
            });
          }
        });
    });
});
