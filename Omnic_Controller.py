import time
import shutil
import os
from PyQt5 import QtCore

from Device_Communicator import Device_Communicator

class Omnic_Controller( QtCore.QObject ):
	"""Interface with Omnic Windows NT Computer"""
	Device_Connected = QtCore.pyqtSignal(str,str)
	Device_Disconnected = QtCore.pyqtSignal(str,str)

	def __init__( self, configuration_file, parent ):
		super().__init__( parent )
		self.got_file_over_tcp = False

		self.response_function = lambda ftir_file_contents : None
		self.ip_range = configuration_file['Omnic_Communicator']['ip_range']
		try:
			self.device_communicator = Device_Communicator( parent, identifier_string=configuration_file['Omnic_Communicator']['Listener_Type'], listener_address=None,
												  port=configuration_file['Omnic_Communicator']['Listener_Port'], timeout_ms=120000 )
			self.device_communicator.Reply_Recieved.connect( lambda message, device : self.ParseMessage( message ) )
			self.device_communicator.File_Recieved.connect( lambda message, device : self.ParseFile( message ) )
			self.device_communicator.Device_Connected.connect( lambda peer_identifier : self.Device_Connected.emit( peer_identifier, "Wifi" ) )
			self.device_communicator.Device_Disconnected.connect( lambda peer_identifier : self.Device_Disconnected.emit( peer_identifier, "Wifi" ) )
		except:
			self.device_communicator = None
			raise Exception( "Issue setting up network listener, please make sure computer is connected to a router" )


	def ParseMessage( self, message ):
		pass

	def ParseFile( self, message ):
		self.response_function( message )
		self.got_file_over_tcp = True
		pass

	def Update( self ):
		if( self.device_communicator.No_Devices_Connected() ):
			self.device_communicator.Poll_LocalIPs_For_Devices( self.ip_range )

	def SendFile( self, file_path ):
		file = open( "GetBackground.command", 'r' )
		file_contents = file.read()
		file.close()

		self.device_communicator.Send_Command( "FILE " + str(len(file_contents)) + "\n" + file_contents )

	def Measure_Sample( self, measurement_name ):
		print( "Starting measurement: " + measurement_name )
		self.SendFile( "GetBackground.command" )
		return

	def Set_Response_Function( self, response_function ):
		self.response_function = response_function
