import base64
import string
import random
import hashlib
import sys

from Crypto.Cipher import AES


iv = '@@@@&&&&####$$$$'
BLOCK_SIZE = 16

if (sys.version_info > (3, 0)):
	__pad__ = lambda s: bytes(s + (BLOCK_SIZE - len(s) % BLOCK_SIZE) * chr(BLOCK_SIZE - len(s) % BLOCK_SIZE), 'utf-8')
else:
	__pad__ = lambda s: s + (BLOCK_SIZE - len(s) % BLOCK_SIZE) * chr(BLOCK_SIZE - len(s) % BLOCK_SIZE)

__unpad__ = lambda s: s[0:-ord(s[-1])]

def encrypt(input, key):
	input = __pad__(input)
	c = AES.new(key.encode("utf8"), AES.MODE_CBC, iv.encode("utf8"))
	input = c.encrypt(input)
	input = base64.b64encode(input)
	return input.decode("UTF-8")

def decrypt(encrypted, key):
	encrypted = base64.b64decode(encrypted)
	c = AES.new(key.encode("utf8"), AES.MODE_CBC, iv.encode("utf8"))
	param = c.decrypt(encrypted)
	if type(param) == bytes:
		param = param.decode()
	return __unpad__(param)

def generateSignature(params, key):
	if not type(params) is dict and not type(params) is str:
		raise Exception("string or dict expected, " + str(type(params)) + " given")
	if type(params) is dict:
		params = getStringByParams(params)
	return generateSignatureByString(params, key)

def verifySignature(params, key, checksum):
	if not type(params) is dict and not type(params) is str:
		raise Exception("string or dict expected, " + str(type(params)) + " given")
	if "CHECKSUMHASH" in params:
		del params["CHECKSUMHASH"]
		
	if type(params) is dict:
		params = getStringByParams(params)
	return verifySignatureByString(params, key, checksum)

def generateSignatureByString(params, key):
	salt = generateRandomString(4)
	return calculateChecksum(params, key, salt)

def verifySignatureByString(params, key, checksum):
	paytm_hash = decrypt(checksum, key)    
	salt = paytm_hash[-4:]
	return paytm_hash == calculateHash(params, salt)

def generateRandomString(length):
	chars = string.ascii_uppercase + string.digits + string.ascii_lowercase
	return ''.join(random.choice(chars) for _ in range(length))

def getStringByParams(params):
	params_string = []
	for key in sorted(params.keys()):
		value = params[key] if params[key] is not None and params[key].lower() != "null" else ""
		params_string.append(str(value))
	return '|'.join(params_string)

def calculateHash(params, salt):
	finalString = '%s|%s' % (params, salt)
	hasher = hashlib.sha256(finalString.encode())
	hashString = hasher.hexdigest() + salt
	return hashString

def calculateChecksum(params, key, salt): 
	hashString = calculateHash(params, salt)
	return encrypt(hashString, key)