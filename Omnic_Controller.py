import time
import shutil
import os

from Device_Communicator import Device_Communicator

class Omnic_Controller(object):
	"""Interface with Omnic Windows NT Computer"""
	unique_name_number = 0
	def __init__( self, parent, directory_for_commands, directory_for_results ):
		self.directory_for_commands = directory_for_commands
		self.directory_for_results = directory_for_results

		self.remembered_file_list = os.listdir( self.directory_for_results )
		self.response_function = lambda ftir_file_contents : None

		try:
			self.device_communicator = Device_Communicator( parent, identifier_string="Omnic Controller", listener_address=None, port=6542 )
			self.device_communicator.Poll_LocalIPs_For_Devices( "192.168.1-2.2-254" )#'127.0.0.1' )
			success = True
			self.device_communicator.Reply_Recieved.connect( lambda message, device : self.ParseMessage( message ) )
			self.device_communicator.File_Recieved.connect( lambda message, device : self.ParseFile( message ) )
		except:
			self.device_communicator = None
			raise Exception( "Issue setting up network listener, please make sure computer is connected to a router" )


	def ParseMessage( self, message ):
		pass
	def ParseFile( self, message ):
		self.response_function( message )
		pass

	def Update( self ):
		if( self.device_communicator.No_Devices_Connected() ):
			self.device_communicator.Poll_LocalIPs_For_Devices( "192.168.1-2.2-254" )#'127.0.0.1' )

		current_file_list = os.listdir( self.directory_for_results )
		added = [f for f in current_file_list if not f in self.remembered_file_list]
		temporary_folder = '.'
		if( len(added) == 0 ):
			return False

		results_found = False
		time.sleep(2) # Wait 2 seconds to allow file to finish being written
		for f in added:
			file_remote_path = self.directory_for_results + '/' + f
			file_tmp_path = temporary_folder + '/' + f
			shutil.move( file_remote_path, file_tmp_path )
			file = open( file_tmp_path, 'r' )
			file_contents = file.read()
			file.close()

			self.response_function( file_contents )
			print( "Finished measuring: " + f + '\n' )
			results_found = True
			os.remove( file_tmp_path )

		return results_found

	def SendFile( self, file_path ):
		file = open( "GetBackground.command", 'r' )
		file_contents = file.read()
		file.close()

		self.device_communicator.Send_Command( "FILE " + str(len(file_contents)) + "\n" + file_contents )

	def Measure_Background( self, measurement_name ):
		print( "Starting measurement: " + measurement_name + '\n' )
		self.SendFile( "GetBackground.command" )
		return

		print( "Starting measurement: " + measurement_name + '\n' )
		file = open( "GetBackground.command", 'r' )
		file_contents = file.read()
		file.close()

		file_contents = file_contents.replace( 'MeasurementName', measurement_name )
		output_command_file = open( self.directory_for_commands + r'\GetBackground' + str(Omnic_Controller.unique_name_number) + '.command', 'w' )
		Omnic_Controller.unique_name_number += 1
		output_command_file.write( file_contents )
		output_command_file.close()

	def Measure_Sample( self, measurement_name ):
		SendFile( "GetSample.command" )
		return

		file = open( "GetSample.command", 'r' )
		file_contents = file.read()
		file.close()

		file_contents.replace( '$MeasurementName', measurement_name )
		output_command_file = open( self.directory_for_commands + r'\GetSample' + str(Omnic_Controller.unique_name_number) + '.command', 'w' )
		Omnic_Controller.unique_name_number += 1
		output_command_file.write( file_contents )
		output_command_file.close()

	def Set_Response_Function( self, response_function ):
		self.response_function = response_function
