import time
import shutil
import os

#try:
#	from watchdog.observers import Observer
#	from watchdog.events import FileSystemEventHandler
#except:
#	print( 'Need to install watchdog, run: pip install watchdog' )
#	exit()


class Omnic_Controller(object):
	"""Interface with Omnic Windows NT Computer"""
	unique_name_number = 0
	def __init__( self, directory_for_commands, directory_for_results ):
		self.directory_for_commands = directory_for_commands
		self.directory_for_results = directory_for_results

		#self.observer = Observer()
		#self.event_handler = Handler()
		#self.observer.schedule( self.event_handler, self.directory_for_results, recursive=False )
		#self.observer.start()

		self.remembered_file_list = os.listdir( self.directory_for_results )
		self.response_function = lambda file_location, file_name : None

	def Update( self ):
		current_file_list = os.listdir( self.directory_for_results )
		added = [f for f in current_file_list if not f in self.remembered_file_list]
		temporary_folder = './TestOutput'
		if( len(added) == 0 ):
			return False

		results_found = False
		time.sleep(2) # Wait 2 seconds to allow file to finish being written
		for f in added:
			file_remote_path = self.directory_for_results + '/' + f
			file_tmp_path = temporary_folder + '/' + f
			shutil.move( file_remote_path, file_tmp_path )
			self.response_function( temporary_folder, f )
			print( "Finished measuring: " + f + '\n' )
			results_found = True

		return results_found


	def Measure_Background( self, measurement_name ):
		print( "Starting measurement: " + measurement_name + '\n' )
		file = open( "GetBackground.command", 'r' )
		file_contents = file.read()
		file.close()

		file_contents.replace( '$MeasurementName', measurement_name )
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
		#self.event_handler.Set_Response_Function( response_function )


#class Handler( FileSystemEventHandler ):
#	def __init__( self ):
#		self.unique_number = 0
#		self.response_function = lambda file_path : None

#	def Set_Response_Function( self, response_function ):
#		self.response_function = response_function
#	def on_created(self, event):
#		if event.is_directory:
#			return None

#		#	elif event.event_type == 'created':
#		# Take any action here when a file is first created.
#		print( "Received created event - %s." % event.src_path )

#		time.sleep(2) # Wait 2 seconds to allow file to finish being written
#		try:
#			file_moved_path = './TestOutput' + str(self.unique_number)+ ".csv"
#			shutil.move( event.src_path, file_moved_path )
#			self.response_function( file_moved_path )
#			self.unique_number += 1
#		except OSError:
#			pass # Sometimes duplicate events are created, the first one will work and subsequent will have errors


#	#@staticmethod
#	#def on_any_event(event):
#	#	if event.is_directory:
#	#		return None

#	#	elif event.event_type == 'created':
#	#		# Take any action here when a file is first created.
#	#		print( "Received created event - %s." % event.src_path )

#	#		time.sleep(2) # Wait 2 seconds to allow file to finish being written
#	#		try:
#	#			shutil.move( event.src_path, './TestOutput' + str(Handler.unique_number)+ ".csv" )
#	#			Handler.unique_number += 1
#	#		except:
#	#			pass # Sometimes duplicate events are created, the first one will work and subsequent will have errors

#	#	elif event.event_type == 'modified':
#	#		# Taken any action here when a file is modified.
#	#		pass
#	#		#print( "Received modified event - %s." % event.src_path )
