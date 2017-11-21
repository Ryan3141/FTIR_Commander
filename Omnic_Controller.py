import time
import shutil

try:
	from watchdog.observers import Observer
	from watchdog.events import FileSystemEventHandler
except:
	print( 'Need to install watchdog, run: pip install watchdog' )
	exit()


class Omnic_Controller(object):
	"""Interface with Omnic Windows NT Computer"""
	unique_name_number = 0
	def __init__( self, directory_for_commands, directory_for_results ):
		self.directory_for_commands = directory_for_commands
		self.directory_for_results = directory_for_results
		self.observer = Observer()

		self.event_handler = Handler()
		self.observer.schedule( self.event_handler, self.directory_for_results, recursive=True )
		self.observer.start()

	def Measure_Background( self, measurement_name ):
		file = open( "GetBackground.command", 'r' )
		file_contents = file.read()
		file.close()

		#file_contents.replace( '$MeasurementName')
		output_command_file = open( self.directory_for_commands + r'\GetBackground' + str(Omnic_Controller.unique_name_number) + '.command', 'w' )
		Omnic_Controller.unique_name_number += 1
		output_command_file.write( file_contents )
		output_command_file.close()

	def Measure_Sample( self, measurement_name ):
		file = open( "GetSample.command", 'r' )
		file_contents = file.read()
		file.close()

		#file_contents.replace( '$MeasurementName')
		output_command_file = open( self.directory_for_commands + r'\GetSample' + str(Omnic_Controller.unique_name_number) + '.command', 'w' )
		Omnic_Controller.unique_name_number += 1
		output_command_file.write( file_contents )
		output_command_file.close()

class Handler( FileSystemEventHandler ):
	unique_number = 0
	@staticmethod
	def on_any_event(event):
		if event.is_directory:
			return None

		elif event.event_type == 'created':
			# Take any action here when a file is first created.
			print( "Received created event - %s." % event.src_path )

			time.sleep(2)
			try:
				shutil.move( event.src_path, './TestOutput' + str(Handler.unique_number)+ ".csv" )
				Handler.unique_number += 1
			except:
				pass # Sometimes duplicate events are created, the first one will work and subsequent will have errors

		elif event.event_type == 'modified':
			# Taken any action here when a file is modified.
			pass
			#print( "Received modified event - %s." % event.src_path )
