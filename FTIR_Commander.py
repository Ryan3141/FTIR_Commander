import time
import os
import sqlite3
from sqlite3 import Error
import hashlib
import numpy as np
from datetime import datetime

from Temperature_Controller import Temperature_Controller
from Omnic_Controller import Omnic_Controller

#var = input("Enter something: ")
#ser.write(var.encode())

class main_application:
	def __init__( self ):
		self.temp_controller = Temperature_Controller()
		self.temp_read_start = time.time()
		self.file_watch_start = time.time()
		self.Connect_To_SQL()
		self.omnic_controller = Omnic_Controller( directory_for_commands=r"\\NICCOMP\ExportData\Commands", directory_for_results=r"\\NICCOMP\ExportData\Test" )
		#self.omnic_controller = Omnic_Controller( directory_for_commands=r"C:\Users\Ryan\Documents\Visual Studio 2017\Projects\FTIR_Commander\FTIR_Commander\Commands", directory_for_results=r"C:\Users\Ryan\Documents\Visual Studio 2017\Projects\FTIR_Commander\FTIR_Commander\Outputs" )

	def Connect_To_SQL( self ):
		try:
			self.sql_conn = sqlite3.connect( "FTIR_Data.db" )
		except Error as e:
			print( e )

	def main_loop( self, sample_name, temperature, bias ):
		self.omnic_controller.Set_Response_Function(
			lambda file_location, file_name :
			self.Deal_With_FTIR_Data( file_location, file_name, self.sql_conn,
					sample_name, temperature, bias ) )
		self.temp_controller.Set_Temperature_In_K( temperature )

		while( True ):
			new_time = time.time()

			if( new_time - self.temp_read_start > 0.5 ):
				self.temp_controller.Update()
				print( self.temp_controller.Get_Temperature_In_K() )
				self.temp_read_start = new_time

			if( self.temp_controller.Temperature_Is_Stable() ):
				print( "Temperature stable around: " + str(self.temp_controller.setpoint_temperature) + '\n' )
				self.omnic_controller.Measure_Background( sample_name )
				break
				#self.omnic_controller.Measure_Sample('test')
			time.sleep(0.1) # Yield attention to not hog the processor

		while( True ):
			new_time = time.time()

			if( new_time - self.temp_read_start > 0.5 ):
				self.temp_controller.Update()
				print( self.temp_controller.Get_Temperature_In_K() )
				self.temp_read_start = new_time

			if( new_time - self.file_watch_start > 0.5 ):
				if( self.omnic_controller.Update() ):
					break
				self.file_watch_start = new_time

			time.sleep(0.1) # Yield attention to not hog the processor

	def Deal_With_FTIR_Data( self, file_location, file_name, sql_conn, sample_name, temperature_in_k, bias_in_v ):
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

	app = main_application()
	sample_name = "ZnS Window"
	#temperatures_to_measure = range( 80, 301, 10 )
	temperatures_to_measure = range( 295, 311, 11 )
	biases_to_measure = np.linspace( 0, 1, 1 )

	try:
		for temperature in temperatures_to_measure:
			for bias in biases_to_measure:
				app.main_loop( sample_name, temperature, bias )
	except OSError:
		print( "Lost Connection With: " + r"\\NICCOMP" )
	#except:
	#	print( "Error" )
	#	omnic_controller.observer.stop()
	#	omnic_controller.observer.join()

