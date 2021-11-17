from __future__ import unicode_literals
import frappe
from pymysql import InternalError
import requests
import base64
import json      
from frappe.utils import get_files_path


@frappe.whitelist()
def capture_fast_ocr(doctype, file_dir):
    filename = file_dir.replace("/private/files/", "")
    file_path = get_files_path(filename, is_private=True)

    headers = {'content-type' : 'application/x-www-form-urlencoded'}
    authRequest = { 'username' : 'marief.rahman279@gmail.com',
                    'password' : 'P@55w0rd123!',
                    'grant_type' : 'password'
                    }
    
    response = requests.request("POST", "https://api.capturefast.com/token", headers=headers, data=authRequest)
    accessToken = response.json().get('access_token')

    file_content = ""
    with open(file_path, "rb") as f:
        file_content = base64.b64encode(f.read()).decode('ascii')

    headers = {'content-type' : 'application/json',
               'Authorization' : 'Bearer ' + accessToken
               }

    document = {"TeamId" : '5014',
                "DocumentTypeId" : "12148",
                "Files" : [{'FileName' : filename, "Content" : file_content}]
                }

    response = requests.request("POST", "https://api.capturefast.com/api/Upload/Document", 
                                        headers = headers, 
                                        data = json.dumps(document))

    docid = response.json().get("DocumentId")

    jsonDoc = get_result_capturefast(docid, accessToken, timeoutinseconds=100)    
    return jsonDoc

def get_result_capturefast(docid, accessToken, timeoutinseconds=100):
    headers = {
        'content-type': 'application/json',
        'Authorization': 'Bearer ' + accessToken
    }

    jsonDoc = {}
    response = requests.request("GET",
                                        "https://api.capturefast.com/Api/Download/Data?documentId=" + str(docid),
                                        headers=headers)    
    jsonDoc = response.json()

    while(timeoutinseconds > 0):
        timeoutinseconds -= 5

        if(timeoutinseconds < 0):
            raise Exception("Sorry, data is not available")

        try:
            response = requests.request("GET",
                                        "https://api.capturefast.com/api/Download/Data?documentId=" + str(docid),
                                        headers=headers)
        except Exception as ex:
            raise Exception("Capturefast Communication Error")

        jsonDoc = response.json()
        resultCode = jsonDoc['ResultCode']

        if(resultCode == 0):
            break
        elif(resultCode == 100):
            continue
        else:
            time.sleep(5)
            jsonDoc = get_result_capturefast(docid, accessToken, timeoutinseconds)
            break
    
    return jsonDoc
