import time
import shutil
import os


class Omnic_Controller(object):
	"""Interface with Omnic Windows NT Computer"""
	unique_name_number = 0
	def __init__( self, directory_for_commands, directory_for_results ):
		self.directory_for_commands = directory_for_commands
		self.directory_for_results = directory_for_results

		self.remembered_file_list = os.listdir( self.directory_for_results )
		self.response_function = lambda file_location, file_name : None
		self.unchecked_new_files = []

	def Update( self ):
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
			self.response_function( temporary_folder, f )
			self.unchecked_new_files.append( ( temporary_folder, f ) )
			print( "Finished measuring: " + f + '\n' )
			results_found = True

		return results_found


	def Measure_Background( self, measurement_name ):
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
