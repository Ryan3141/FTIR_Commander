import time
import shutil
import os
import configparser
from PyQt5 import QtCore

from MPL_Shared.Device_Communicator import Device_Communicator
from .FTIR_Config_File import Load_FTIR_Config

class Omnic_Controller( QtCore.QObject ):
	"""Interface with Omnic Windows NT Computer"""
	Device_Connected = QtCore.pyqtSignal(str,str)
	Device_Disconnected = QtCore.pyqtSignal(str,str)
	File_Recieved = QtCore.pyqtSignal( str, bytes, dict ) # file_name, file_contents, ftir_settings
	Settings_File_Recieved = QtCore.pyqtSignal( dict )

	def __init__( self, configuration_file, parent=None ):
		super().__init__( parent )
		self.got_file_over_tcp = False
		self.settings = {}
		self.configuration_file = configuration_file

	def thread_start( self ):
		config = configparser.ConfigParser()
		config.read( self.configuration_file )

		self.ip_range = config['Omnic_Communicator']['ip_range']
		try:
			self.device_communicator = Device_Communicator( self, identifier_string=config['Omnic_Communicator']['Listener_Type'], listener_address=None,
												  port=config['Omnic_Communicator']['Listener_Port'], timeout_ms=12000000 )
			self.device_communicator.Reply_Recieved.connect( lambda message, device : self.ParseMessage( message ) )
			self.device_communicator.File_Recieved.connect( lambda file_name, file_contents, device : self.ParseFile( file_name, file_contents ) )
			self.device_communicator.Device_Connected.connect( lambda peer_identifier : self.Device_Connected.emit( peer_identifier, "Wifi" ) )
			self.device_communicator.Device_Disconnected.connect( lambda peer_identifier : self.Device_Disconnected.emit( peer_identifier, "Wifi" ) )
		except Exception:
			self.device_communicator = None
			raise Exception( "Issue setting up network listener, please make sure computer is connected to a router" )

		# Continuously recheck omnic (FTIR) controller
		self.omnic_recheck_timer = QtCore.QTimer( self )
		self.omnic_recheck_timer.timeout.connect( self.Update )
		self.omnic_recheck_timer.start( 500 )


	def ParseMessage( self, message ):
		if message == 'Ping':
			return
		#split_values = message.split(' ')
		#name = split_values[0]
		#value = ' '.join( split_values[1:] )
		#self.settings[ name ] = value
		#print( message )

	def ParseFile( self, file_name, file_contents ):
		if file_name.lower() == "settingsfile.exp" or file_name.lower() == "default.exp":
			self.settings = Load_FTIR_Config( file_contents )
			self.Settings_File_Recieved.emit( self.settings )
			print( "Got FTIR Configuration File" )
			return
		self.File_Recieved.emit( file_name, file_contents, self.settings )
		self.got_file_over_tcp = True

	def Update( self ):
		if( self.device_communicator.No_Devices_Connected() ):
			self.device_communicator.Poll_LocalIPs_For_Devices( self.ip_range )

	def SendFile( self, folder, file_path ):
		file = open( os.path.join(folder, file_path), 'r' )
		file_contents = file.read()
		file.close()

		self.device_communicator.Send_Command( "FILE " + str(len(file_contents)) + "\n" + file_contents )

	def Measure_Sample( self, folder="." ):
		self.SendFile( folder, "GetBackground.command" )

	def Request_Settings( self, folder="." ):
		print( "Request settings" )
		self.SendFile( folder, "SaveSettingsFile.command" ) # Make sure the settings file is saved as settings_file.exp (case insensitive) to get it the right place
