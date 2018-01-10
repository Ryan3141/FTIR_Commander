import time
import os
import sqlite3
import hashlib
import numpy as np
from datetime import datetime

from Temperature_Controller import Temperature_Controller
from Omnic_Controller import Omnic_Controller
class ftir_application:
	def __init__( self, directory_for_commands, directory_for_results ):
		self.temp_controller = Temperature_Controller()
		self.temp_controller.Turn_Off()
		self.temp_read_start = time.time()
		self.file_watch_start = time.time()
		self.Connect_To_SQL()
		self.omnic_controller = Omnic_Controller( directory_for_commands, directory_for_results )

	def Connect_To_SQL( self ):
		try:
			self.sql_conn = sqlite3.connect( "FTIR_Data.db" )
		except sqlite3.Error as e:
			print( e )

		Create_Table_If_Needed( self.sql_conn )

	def Update_Temperature_Reading( self, new_time ):
		if( new_time - self.temp_read_start > 0.5 ):
			self.temp_controller.Update()
			print( self.temp_controller.Get_Temperature_In_K() )
			self.temp_read_start = new_time

	def Start_Measurement_When_Temperature_Stable( self, sample_name ):
		new_time = time.time()

		self.Update_Temperature_Reading( new_time )

		if( self.temp_controller.setpoint_temperature is None ):
			print( "Starting Measurement\n" )
			self.omnic_controller.Measure_Background( sample_name )
			return True
		elif( self.temp_controller.Temperature_Is_Stable() ):
			print( "Temperature stable around: " + str(self.temp_controller.setpoint_temperature) + '\n' )
			print( "Starting Measurement\n" )
			self.omnic_controller.Measure_Background( sample_name )
			return True
			#self.omnic_controller.Measure_Sample('test')
		return False

	def Wait_For_Results_File( self ):
		new_time = time.time()

		self.Update_Temperature_Reading( new_time )

		if( new_time - self.file_watch_start > 0.5 ):
			if( self.omnic_controller.Update() ):
				return True
			self.file_watch_start = new_time

		return False

	def Run_Sweep( self, sample_name, temperatures_to_measure, biases_to_measure ):
		for temperature in temperatures_to_measure:
			for bias in biases_to_measure:
				self.omnic_controller.Set_Response_Function(
					lambda file_location, file_name :
					Deal_With_FTIR_Data( file_location, file_name, self.sql_conn,
							sample_name, temperature, bias ) )
				if( temperature ): # None is ok, just means we don't know the temperature
					self.temp_controller.Set_Temperature_In_K( temperature )
					self.temp_controller.Turn_On()

				while(True):
					if( self.Start_Measurement_When_Temperature_Stable( sample_name ) ):
						break
					yield(False)

				while(True):
					if( self.Wait_For_Results_File() ):
						break
					yield(False)

		self.temp_controller.Turn_Off()
		yield(True)

def Create_Table_If_Needed( sql_conn ):
	cur = sql_conn.cursor()
	try:
		cur.execute("""CREATE TABLE `ftir_measurements` ( `sample_name` TEXT NOT NULL, `time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, `measurement_id` TEXT NOT NULL, `temperature_in_k` REAL, `bias_in_v` REAL )""")
	except:
		pass # Will cause exception if they already exist, but that's fine since we are just trying to make sure they exist
	try:
		cur.execute("""CREATE TABLE `raw_ftir_data` ( `measurement_id` TEXT NOT NULL, `wavenumber` REAL NOT NULL, `intensity` REAL NOT NULL );""")
	except:
		pass # Will cause exception if they already exist, but that's fine since we are just trying to make sure they exist

	cur.close()
	return False

def Deal_With_FTIR_Data( file_location, file_name, sql_conn, sample_name, temperature_in_k, bias_in_v ):
	full_path = file_location + '/' + file_name
	file = open( full_path, 'r' )
	file_contents = file.read()
	file.close()

	#output_command_file = open( './test_auto.csv', 'w' )
	#output_command_file.write( file_contents )
	#output_command_file.close()

	wave_number = []
	intensity = []
	for line in file_contents.split('\n'):
		data_split = line.split(',')
		if len( data_split ) < 2:
			continue
		wave_number.append( data_split[0] )
		intensity.append( data_split[1] )

	m = hashlib.sha256()
	#m.update( 'Test'.encode() )
	m.update( (sample_name + str( datetime.now() ) + ','.join(intensity) ).encode() )
	measurement_id = m.hexdigest()
	meta_data_sql_string = '''INSERT INTO ftir_measurements(sample_name,measurement_id,temperature_in_k,bias_in_v) VALUES(?,?,?,?)'''
	data_sql_string = '''INSERT INTO raw_ftir_data(measurement_id,wavenumber,intensity) VALUES(?,?,?)'''
	cur = sql_conn.cursor()
	cur.execute( meta_data_sql_string, (sample_name,measurement_id,temperature_in_k,bias_in_v) )
	cur.executemany( data_sql_string, zip([measurement_id for x in range(len(wave_number))],wave_number,intensity) )
	sql_conn.commit()

	os.remove( full_path )




if( __name__ == "__main__" ):

	app = ftir_application( directory_for_commands=r"\\NICCOMP\ExportData\Commands", directory_for_results=r"\\NICCOMP\ExportData\Output" )
	#app = ftir_application( directory_for_commands=r"C:\Users\Ryan\Documents\Visual Studio 2017\Projects\FTIR_Commander\FTIR_Commander\Commands", directory_for_results=r"C:\Users\Ryan\Documents\Visual Studio 2017\Projects\FTIR_Commander\FTIR_Commander\Outputs" )
	sample_name = "ZnSe Window"
	#temperatures_to_measure = range( 80, 301, 10 )
	lambda temperature_in_k : None
	temperatures_to_measure = range( 297, 311, 11 )
	biases_to_measure = np.linspace( 0, 1, 1 )

	try:
		running_process = app.Run_Sweep( sample_name, temperatures_to_measure, biases_to_measure )
		for x in running_process:
			if x:
				break
			time.sleep(0.1) # Yield attention to not hog the processor

	except OSError:
		print( "Lost Connection With: " + r"\\NICCOMP" )
