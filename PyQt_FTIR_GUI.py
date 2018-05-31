from PyQt5 import QtNetwork, QtCore, QtGui, uic, QtWidgets
import os
import sys
import sqlite3
try:
	import MySQLdb
except:
	print( "Need to install mysql plugin, run: pip install mysqlclient")
	exit()
import hashlib
from datetime import datetime
import re
import configparser

import numpy as np
from Temperature_Controller import Temperature_Controller
from Omnic_Controller import Omnic_Controller
from Graph import Graph


qtCreatorFile = "PyQt_FTIR_GUI.ui" # GUI layout file.

Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)

def toFloatOrNone( as_string ):
	try:
		return float( as_string )
	except:
		return None

class MyApp(QtWidgets.QMainWindow, Ui_MainWindow):

	#Set_New_Temperature_K = QtCore.pyqtSignal(float)
	#Turn_Off_Temperature_Control = QtCore.pyqtSignal(float)
	def __init__(self):
		QtWidgets.QMainWindow.__init__(self)
		Ui_MainWindow.__init__(self)
		self.setupUi(self)

		self.Init_Subsystems()
		self.Connect_Control_Logic()

		self.temperature_graph.set_title("Measured Temperature Next To Sample")
		self.temperature_graph.setContentsMargins(0, 0, 0, 0)


	def Init_Subsystems( self ):
		config = configparser.ConfigParser()
		config.read('configuration.ini')

		self.Connect_To_SQL( config )
		self.temp_controller = Temperature_Controller( config, parent=self )
		self.omnic_controller = Omnic_Controller( config, parent=self )
		temp_controller_recheck_timer = QtCore.QTimer( self )
		temp_controller_recheck_timer.timeout.connect( self.temp_controller.Update )
		temp_controller_recheck_timer.start( 500 )
		omnic_recheck_timer = QtCore.QTimer( self )
		omnic_recheck_timer.timeout.connect( lambda : self.omnic_controller.Update() )
		omnic_recheck_timer.start( 500 )
		self.Temp_Controller_Disconnected()
		self.Omnic_Disconnected()
		self.temp_controller.Device_Connected.connect( self.Temp_Controller_Connected )
		self.temp_controller.Device_Disconnected.connect( self.Temp_Controller_Disconnected )
		self.omnic_controller.Device_Connected.connect( self.Omnic_Connected )
		self.omnic_controller.Device_Disconnected.connect( self.Omnic_Disconnected )
		#self.setTemperature_pushButton.clicked.connect( lambda : self.Start_Set_Temperature( float(self.currentTemperature_lineEdit.text()) ) )
		self.Stop_Set_Temperature()

		user = config['Omnic_Communicator']['user']
		if user:
			self.user_lineEdit.setText( user )


	def Temp_Controller_Connected( self, identifier, type_of_connection ):
		self.tempControllerConnected_label.setText( str(identifier) + " Connected" )
		self.tempControllerConnected_label.setStyleSheet("QLabel { background-color: rgba(0,255,0,255); color: rgba(0, 0, 0,255) }")

	def Temp_Controller_Disconnected( self ):
		self.tempControllerConnected_label.setText( "Temperature Controller Not Connected" )
		self.tempControllerConnected_label.setStyleSheet("QLabel { background-color: rgba(255,0,0,255); color: rgba(0, 0, 0,255) }")

	def Omnic_Connected( self, ip_address ):
		self.omnicConnected_label.setText( "Omnic Connected at " + str(ip_address) )
		self.omnicConnected_label.setStyleSheet("QLabel { background-color: rgba(0,255,0,255); color: rgba(0, 0, 0,255) }")

	def Omnic_Disconnected( self ):
		self.omnicConnected_label.setText( "Omnic Not Connected" )
		self.omnicConnected_label.setStyleSheet("QLabel { background-color: rgba(255,0,0,255); color: rgba(0, 0, 0,255) }")

	def Connect_Control_Logic( self ):
		self.Stop_Measurment()
		self.run_pushButton.clicked.connect( self.Start_Measurement )

		self.temp_controller.Temperature_Changed.connect( self.Temperature_Update )

	def Temperature_Update( self, temperature ):
		#print( "Temp: " + str(QtCore.QDateTime.currentDateTime()) )
		#print( "Temp: " + str(temperature) )
		self.temperature_graph.add_new_data_point( QtCore.QDateTime.currentDateTime(), temperature )

	def Connect_To_SQL( self, configuration_file ):
		try:
			if configuration_file['SQL_Server']['database_type'] == "QSQLITE":
				self.sql_conn = sqlite3.connect( configuration_file['SQL_Server']['database_name'] )
			elif configuration_file['SQL_Server']['database_type'] == "QMYSQL":
				self.sql_conn = MySQLdb.connect(host=configuration_file['SQL_Server']['host_location'],db=configuration_file['SQL_Server']['database_name'],
									user=configuration_file['SQL_Server']['username'],passwd=configuration_file['SQL_Server']['password'])
				self.sql_conn.ping( True ) # Maintain connection to avoid timing out
			self.sql_type = configuration_file['SQL_Server']['database_type']
		except sqlite3.Error as e:
			error = QtWidgets.QMessageBox()
			error.setIcon( QtWidgets.QMessageBox.Critical )
			error.setText( e )
			error.setWindowTitle( "Unable to connect to SQL Database" )
			error.exec_()
			print( e )
			return

		Create_Table_If_Needed( self.sql_conn, self.sql_type )


	def Start_Measurement( self ):
		temp_start, temp_end, temp_step = float(self.lowerTemp_lineEdit.text()), float(self.upperTemp_lineEdit.text()), float(self.stepTemp_lineEdit.text())
		v_start, v_end, v_step = float(self.lowerVoltage_lineEdit.text()), float(self.upperVoltage_lineEdit.text()), float(self.stepVoltage_lineEdit.text())
		
		sample_name = self.sampleName_lineEdit.text()
		user = str( self.user_lineEdit.text() )
		if( sample_name == "" or user == "" ):
			error = QtWidgets.QMessageBox()
			error.setIcon( QtWidgets.QMessageBox.Critical )
			error.setText( "Must enter a sample name and user" )
			error.setWindowTitle( "Error" )
			error.exec_()
			return
		if( self.temp_checkBox.isChecked() ):
			temperatures_to_measure = np.arange( temp_start, temp_end + temp_step, temp_step )
		else:
			temperatures_to_measure = [None]
		if( self.voltage_checkBox.isChecked() ):
			biases_to_measure = np.arange( v_start, v_end + v_step, v_step )
		else:
			biases_to_measure = [None]

		self.run_pushButton.clicked.disconnect()
		self.run_pushButton.setText( "Stop Measurement" )
		self.run_pushButton.setStyleSheet("QPushButton { background-color: rgba(255,0,0,255); color: rgba(0, 0, 0,255); }")
		self.run_pushButton.clicked.connect( self.Stop_Measurment )

		self.omnic_controller.Request_Settings()
		self.Run_Measurment_Loop( sample_name, user, temperatures_to_measure, biases_to_measure )

	def Stop_Measurment( self ):
		if self.temp_controller is not None:
			self.temp_controller.Turn_Off()
			self.temperature_graph.setpoint_temperature = None

		self.omnic_controller.Set_Response_Function(
			lambda file_name, file_contents : None )

		try: self.run_pushButton.clicked.disconnect() 
		except Exception: pass
		
		self.run_pushButton.setText( "Run Sweep" )
		self.run_pushButton.setStyleSheet("QPushButton { background-color: rgba(0,255,0,255); color: rgba(0, 0, 0,255); }")
		self.run_pushButton.clicked.connect( self.Start_Measurement )
		self.measurement_running = False

	def Start_Set_Temperature( self, temperature ):
		if temperature is None:
			return

		self.temp_controller.Set_Temperature_In_K( temperature )
		self.temp_controller.Turn_On()
		self.temperature_graph.setpoint_temperature = temperature

		self.setTemperature_pushButton.setText( "Stop Temperature" )
		self.setTemperature_pushButton.setStyleSheet("QPushButton { background-color: rgba(0,255,0,255); color: rgba(0, 0, 0,255); }")
		self.setTemperature_pushButton.clicked.connect( self.Stop_Set_Temperature )

	def Stop_Set_Temperature( self ):
		if self.temp_controller is not None:
			self.temp_controller.Turn_Off()
			self.temperature_graph.setpoint_temperature = None

		self.setTemperature_pushButton.setText( "Hold Temperature" )
		self.setTemperature_pushButton.setStyleSheet("QPushButton { background-color: rgba(255,0,0,255); color: rgba(0, 0, 0,255); }")
		self.setTemperature_pushButton.clicked.connect( lambda : self.Start_Set_Temperature( toFloatOrNone(self.currentTemperature_lineEdit.text()) ) )

	def Wait_For_Stable_Temp( self, temperature ):
		self.temp_controller.Set_Temperature_In_K( temperature )
		self.temp_controller.Turn_On()
		self.temperature_graph.setpoint_temperature = temperature

		while( not self.temp_controller.Temperature_Is_Stable() ):
			QtCore.QCoreApplication.processEvents()
			measurement_still_running = ( self.run_pushButton.text() == "Stop Measurement" )
			if not measurement_still_running:
				print( "Quitting measurment early" )
				return False
		print( "Temperature stable around: " + str(temperature) + '\n' )
		return True

	def Run_Measurment_Loop( self, sample_name, user, temperatures_to_measure, biases_to_measure ):
		for temperature in temperatures_to_measure:
			for bias in biases_to_measure:
				self.omnic_controller.Set_Response_Function(
					lambda file_name, file_contents, user=user, sample_name=sample_name, temperature_in_k=temperature, bias_in_v=bias :
					Deal_With_FTIR_Data( file_contents, user, self.sql_conn, self.sql_type,
						 sample_name, temperature_in_k, bias_in_v, self.omnic_controller.settings ) )
					#Deal_With_FTIR_Data( file_contents, user, self.sql_conn, self.sql_type,
					#		sample_name, temperature, bias ) )

				if( temperature ): # None is ok, just means we don't know the temperature
					should_continue_measurement = self.Wait_For_Stable_Temp( temperature )
					if not should_continue_measurement:
						return

				print( "Starting Measurement\n" )
				self.omnic_controller.Measure_Sample( sample_name )

				while( not self.omnic_controller.got_file_over_tcp ):
					QtCore.QCoreApplication.processEvents()
					#measurement_still_running = ( self.run_pushButton.text() == "Stop Measurement" )
					#if not measurement_still_running:
					#	print( "Quitting measurment early" )
					#	return False

				self.omnic_controller.got_file_over_tcp = False

		self.Stop_Measurment()
		print( "Finished Measurment" )


def Create_Table_If_Needed( sql_conn, sql_type ):
	cur = sql_conn.cursor()
	try:
		if sql_type == "QSQLITE":
			cur.execute("""CREATE TABLE `ftir_measurements` ( `sample_name`	TEXT NOT NULL, `time`	DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, `measurement_id`	TEXT NOT NULL, `temperature_in_k`	REAL, `bias_in_v`	REAL, `user`	TEXT, `detector`	TEXT, `beam_splitter`	TEXT, `start_wave_number`	REAL, `end_wave_number`	REAL, `number_of_scans`	INTEGER, `velocity`	REAL, `aperture`	REAL, `gain`	REAL );""")
		else:
			cur.execute("""CREATE TABLE `ftir_measurements` ( `sample_name`	TEXT NOT NULL, `time`	DATETIME NOT NULL, `measurement_id`	TEXT NOT NULL, `temperature_in_k`	REAL, `bias_in_v`	REAL, `user`	TEXT, `detector`	TEXT, `beam_splitter`	TEXT, `start_wave_number`	REAL, `end_wave_number`	REAL, `number_of_scans`	INTEGER, `velocity`	REAL, `aperture`	REAL, `gain`	REAL );""")
	except (MySQLdb.Error, MySQLdb.Warning) as e:
		pass
		#print(e)
	except:
		pass # Will cause exception if they already exist, but that's fine since we are just trying to make sure they exist

	try:
		cur.execute("""CREATE TABLE `raw_ftir_data` ( `measurement_id` TEXT NOT NULL, `wavenumber` REAL NOT NULL, `intensity` REAL NOT NULL );""")
	except:
		pass # Will cause exception if they already exist, but that's fine since we are just trying to make sure they exist

	cur.close()
	return False

def Deal_With_FTIR_Data( ftir_file_contents, user, sql_conn, sql_type, sample_name, temperature_in_k, bias_in_v, settings ):
	#output_command_file = open( './test_auto.csv', 'w' )
	#output_command_file.write( file_contents )
	#output_command_file.close()

	wave_number = []
	intensity = []
	for line in re.split( '\n|\r', ftir_file_contents.decode('utf8', 'ignore') ):
		data_split = line.split(',')
		if len( data_split ) < 2:
			continue
		wave_number.append( data_split[0] )
		intensity.append( data_split[1] )

	m = hashlib.sha256()
	#m.update( 'Test'.encode() )
	m.update( (sample_name + str( datetime.now() ) + ','.join(intensity) ).encode() )
	measurement_id = m.hexdigest()
	if sql_type == 'QSQLITE':
		meta_data_sql_string = '''INSERT INTO ftir_measurements(sample_name,user,measurement_id,temperature_in_k,bias_in_v,detector,beam_splitter,start_wave_number,end_wave_number,number_of_scans,velocity,aperture,gain) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)'''
		data_sql_string = '''INSERT INTO raw_ftir_data(measurement_id,wavenumber,intensity) VALUES(?,?,?)'''
	else:
		meta_data_sql_string = '''INSERT INTO ftir_measurements(sample_name,user,measurement_id,temperature_in_k,bias_in_v,detector,beam_splitter,start_wave_number,end_wave_number,number_of_scans,velocity,aperture,gain,time) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())'''
		data_sql_string = '''INSERT INTO raw_ftir_data(measurement_id,wavenumber,intensity) VALUES(%s,%s,%s)'''
	cur = sql_conn.cursor()
	cur.execute( meta_data_sql_string, (sample_name,user,measurement_id,temperature_in_k,bias_in_v, settings["Detector"], settings["Beam Splitter"], settings["Start Wave Number"], settings["End Wave Number"], settings["Number of Scans"], settings["Velocity"], settings["Aperture"], settings["Gain"] ) )
	cur.executemany( data_sql_string, zip([measurement_id for x in range(len(wave_number))],wave_number,intensity) )
	sql_conn.commit()


if __name__ == "__main__":
	app = QtWidgets.QApplication(sys.argv)
	window = MyApp()
	window.show()
	sys.exit(app.exec_())

