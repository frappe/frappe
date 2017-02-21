from __future__ import unicode_literals
import frappe
from frappe.utils.kickapp.bot_helper import Helpers
keyword_func = {'create':'create_keywords', 'update':'update_keywords', 'delete':'delete_keywords', 'get':'get_keywords'}


class Decision(object):
    prev_client = []
    prev_server = []
    level = {'create':0, 'update':0, 'delete':0, 'get':0 }

    def __init__(self, doctype, query, action):
        self.doctype = doctype
        self.query = query
        self.lower_query = query.lower()
        self.action = action
    
    def reset(self):
        Decision.prev_client[:] = []
        Decision.prev_server[:] = []
    
    def get_prev_client(self):
        return Decision.prev_client
    
    def get_prev_server(self):
        return Decision.prev_server
    
    def push_prev_client(self, message):
        Decision.prev_client.append(message)
    
    def push_prev_server(self, message):
        Decision.prev_server.append(message)
    
    def pop_prev_client(self):
        Decision.prev_client.pop()
    
    def pop_prev_server(self):
        Decision.prev_server.pop()
    
    def has(self, words):
        for word in words:
            if  word in self.lower_query:
                return True
        return False
    
    def generate(self, doctype, method):
        method_name = keyword_func.get(method)
        return getattr(Helpers(), method_name)(doctype)
    
    def get_method(self, method_name):
        return method_name()
    





        
        
        
        
        

    

    # def get_action_with_message(self):
        
        