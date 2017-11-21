try:
	import serial
except:
	print( 'Need to install PySerial, run: pip install PySerial' )
	exit()

import re

class Temperature_Controller(object):
	"""Interface with serial com port to control temperature"""
	def __init__( self ):
		try:
			self.serial_connection = serial.Serial('COM3', 115200, timeout=0)
		except:
			print( "Issue finding serial device, please make sure it is connected")
			exit()
		self.current_temperature = None
		self.setpoint_temperature = None
		self.partial_serial_message = ""

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

	def SetTemp( self, new_temperature ):
		self.serial_connection.write( ("Set Temp " + str(new_temperature)).encode() )

	def GetTemp( self ):
		return self.current_temperature

	def ParseMessage( self, message ):
		pattern = re.compile( r'Thermocouple Temp: (-?\d+\.\d+([eE][-+]?\d+?)?)' ) # Grab any properly formatted floating point number
		m = pattern.match( message )
		if( m ):
			self.current_temperature = float( m.group( 1 ) )



