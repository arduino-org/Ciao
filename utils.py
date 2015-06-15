import os, sys, time, logging
import tty, termios
import re, array
import socket
import hashlib
import settings
from bridgeconnector import BridgeConnector

# enable/disable echo on tty
def enable_echo(fd, enabled):
	(iflag, oflag, cflag, lflag, ispeed, ospeed, cc) = termios.tcgetattr(fd)
	if enabled:
		lflag |= termios.ECHO
	else:
		lflag &= ~termios.ECHO
	new_attr = [iflag, oflag, cflag, lflag, ispeed, ospeed, cc]
	termios.tcsetattr(fd, termios.TCSANOW, new_attr)

# useful function to print out result (to MCU)
def out(status, message, data = None):
	output = [ str(status), str(message) ]
	if not data is None:
		data = serialize(data)
		output.append(data.tostring())
	os.write(sys.stdout.fileno(), ";".join(output))

#COMMAND FUNCTIONS
def clean_command(command):
	return command.rstrip()

def is_valid_command(command):
	#a valid command must contain at least two fields: connector and action
	elements = command.split(";", 2)
	if len(elements) >= 2 and elements[1] in settings.allowed_actions:
		return elements[:2]
	return False, False

#SERIALIZATION FUNCTIONS
# serialize passed dict/list, atm it works only for one level object not nested ones
def serialize(data):
	s = array.array("B")
	entries = []
	if isinstance(data, list):
		for e in data:
			entries.append(escape(e))
	elif isinstance(data, dict):
		for k, v in data.items():
			entries.append(settings.keyvalue_separator.join([escape(k), escape(v)]))
	else:
		entries.append(escape(data))
	s.fromstring(settings.entry_separator.join(entries))
	return s

# unserialize passed dict/list, atm it works only for one level object not nested ones
def unserialize(source, from_array = True):
	#create a clone of original array or a new one from a string
	if from_array:
		data = array.array("B", source)
	else:
		data = array.array("B")
		for c in source:
			data.append(ord(c))

	#identifying data type
	try:
		index = data.index(ord(settings.keyvalue_separator))
		result = {}
	except ValueError, e:
		try:
			index = data.index(ord(settings.entry_separator))
			result = []
		except ValueError, e:
			result = []

	#converting bytearray into object
	addr, size = data.buffer_info()
	count = 0
	if isinstance(result, dict):
		params = ["",""]
		param_index = 0
		while count < size:
			pick = data.pop(0)
			count +=1
			if pick == ord(settings.keyvalue_separator):
				param_index = 1
				params[param_index] = ""
			elif pick == ord(settings.entry_separator):
				result[escape(params[0], False)] = escape(params[1], False)
				param_index = 0
				params = ["", ""]
			else:
				params[param_index] += chr(pick)
		if params[0] != "":
			result[escape(params[0], False)] = escape(params[1], False)
	else:
		entry = ""
		while count < size:
			pick = data.pop(0)
			count +=1
			if pick == ord(settings.entry_separator):
				result.append(escape(entry, False))
				entry = ""
			else:
				entry += chr(pick)
		result.append(escape(entry, False))
	return result

# escape/unescape string for serialization procedure
def escape(s, encode = True):
	if encode:
		return s.encode('unicode-escape')
	else:
		return s.decode('unicode-escape')

# calculate (unique)? checksum from a string
def get_checksum(msg, is_unique = True):
	if not is_unique:
		msg = str(time.time()) + msg
	return hashlib.md5(msg.encode('unicode-escape')).hexdigest()