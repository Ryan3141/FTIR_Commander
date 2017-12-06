try:
	import serial
except:
	print( 'Need to install PySerial, run: pip install PySerial' )
	exit()

import re
import glob
import sys
import numpy as np

class Temperature_Controller(object):
	"""Interface with serial com port to control temperature"""
	def __init__( self ):
		success = False
		for port in GetAvailablePorts():
			try:
				self.serial_connection = serial.Serial(port, 115200, timeout=0)
				success = True
				break
			except:
				pass

		if( not success ):
			print( "Issue finding serial device, please make sure it is connected")
			exit()

		self.current_temperature = None
		self.setpoint_temperature = None
		self.partial_serial_message = ""
		self.past_temperatures = []

	def Update( self ):
		try:
			temp = self.serial_connection.readline()
			self.partial_serial_message += temp.decode("utf-8", "ignore")
			split_into_messages = self.partial_serial_message.split( '\n' )
			self.partial_serial_message = split_into_messages[ -1 ]
			for message in split_into_messages[:-1]:
				self.ParseMessage( message )

#		time.sleep(1)
		except serial.SerialTimeoutException:
			pass
#   		print('Data could not be read')
		#except serial.serialutil.SerialException:
		#	pass

	def Set_Temperature_In_K( self, temperature_in_k ):
		temperature_in_c = temperature_in_k - 273.15
		self.setpoint_temperature = temperature_in_k
		self.serial_connection.write( ("Set Temp " + str(temperature_in_c)).encode() )

	def Get_Temperature_In_K( self ):
		return self.current_temperature

	def ParseMessage( self, message ):
		pattern = re.compile( r'Thermocouple Temp: (-?\d+\.\d+([eE][-+]?\d+?)?)' ) # Grab any properly formatted floating point number
		m = pattern.match( message )
		if( m ):
			self.current_temperature = float( m.group( 1 ) ) + 273.15
			self.past_temperatures.append( self.current_temperature )
			if( len(self.past_temperatures) > 10 ):
				self.past_temperatures = self.past_temperatures[-10:]

	def Temperature_Is_Stable( self ):
		if( len(self.past_temperatures) < 10 ):
			return False
		error = np.array( self.past_temperatures ) - self.setpoint_temperature
		deviation = np.std( error )
		average_error = np.mean( error )
		if( abs(average_error) < 1 and deviation < 0.5 ):
			return True
		else:
			return False

# Function from: https://stackoverflow.com/questions/12090503/listing-available-com-ports-with-python/14224477#14224477
def GetAvailablePorts():
	""" Lists serial port names

		:raises EnvironmentError:
			On unsupported or unknown platforms
		:returns:
			A list of the serial ports available on the system
	"""
	if sys.platform.startswith('win'):
		ports = ['COM%s' % (i + 1) for i in range(256)]
	elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
		# this excludes your current terminal "/dev/tty"
		ports = glob.glob('/dev/tty[A-Za-z]*')
	elif sys.platform.startswith('darwin'):
		ports = glob.glob('/dev/tty.*')
	else:
		raise EnvironmentError('Unsupported platform')

	result = []
	for port in ports:
		try:
			s = serial.Serial(port)
			s.close()
			result.append(port)
		except (OSError, serial.SerialException):
			pass
	return result

