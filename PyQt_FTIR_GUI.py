from PyQt5 import QtNetwork, QtCore, QtGui, uic, QtWidgets
import os
import sys
import sqlite3
import hashlib
from datetime import datetime

import numpy as np
from Temperature_Controller import Temperature_Controller
from Omnic_Controller import Omnic_Controller
from Graph import Graph


qtCreatorFile = "PyQt_FTIR_GUI.ui" # GUI layout file.

Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)

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
		self.Connect_To_SQL()
		self.temp_controller = Temperature_Controller( self )
		#self.omnic_controller = Omnic_Controller( parent=self,
		#						directory_for_commands=r"C:\Users\Ryan\Documents\Visual Studio 2017\Projects\FTIR_Commander\FTIR_Commander\Commands",
		#						directory_for_results=r"C:\Users\Ryan\Documents\Visual Studio 2017\Projects\FTIR_Commander\FTIR_Commander\Outputs" )
		self.omnic_controller = Omnic_Controller( parent=self, directory_for_commands=r"\\NICCOMP\ExportData\Commands", directory_for_results=r"\\NICCOMP\ExportData\Output" )
		recheck_timer = QtCore.QTimer( self )
		recheck_timer.timeout.connect( self.temp_controller.Update )
		recheck_timer.start( 500 )

		#try:
		#	#self.app = ftir_application( directory_for_commands=r"\\NICCOMP\ExportData\Commands", directory_for_results=r"\\NICCOMP\ExportData\Output" )
		#	self.app = ftir_application( directory_for_commands=r"C:\Users\Ryan\Documents\Visual Studio 2017\Projects\FTIR_Commander\FTIR_Commander\Commands",
		#					   directory_for_results=r"C:\Users\Ryan\Documents\Visual Studio 2017\Projects\FTIR_Commander\FTIR_Commander\Outputs" )
		#except Exception as err:
		#	messagebox.showerror( "Error", err )

	def Connect_Control_Logic( self ):
		self.run_pushButton.clicked.connect( self.Start_Measurement )

		self.temp_controller.Temperature_Changed.connect( self.Temperature_Update )

	def Temperature_Update( self, temperature ):
		#print( "Temp: " + str(QtCore.QDateTime.currentDateTime()) )
		#print( "Temp: " + str(temperature) )
		self.temperature_graph.add_new_data_point( QtCore.QDateTime.currentDateTime(), temperature )

	def Connect_To_SQL( self ):
		try:
			self.sql_conn = sqlite3.connect( "FTIR_Data.db" )
		except sqlite3.Error as e:
			error = QtWidgets.QMessageBox()
			error.setIcon( QtWidgets.QMessageBox.Critical )
			error.setText( e )
			error.setWindowTitle( "Unable to connect to SQL Database" )
			error.exec_()
			print( e )
			return

		Create_Table_If_Needed( self.sql_conn )

	def Turn_Off_Temp( self ):
		if( self.temp_controller ):
			self.temp_controller.Turn_Off()

		#for device_id, device in device_communicator.active_connections:
		#	self.device_communicator.Send_Command( ("Turn Off;\n").encode(), device )


	def Start_Measurement( self ):
		temp_start, temp_end, temp_step = float(self.lowerTemp_lineEdit.text()), float(self.upperTemp_lineEdit.text()), float(self.stepTemp_lineEdit.text())
		v_start, v_end, v_step = float(self.lowerVoltage_lineEdit.text()), float(self.upperVoltage_lineEdit.text()), float(self.stepVoltage_lineEdit.text())
		
		sample_name = self.sampleName_lineEdit.text()
		if( sample_name == "" ):
			error = QtWidgets.QMessageBox()
			error.setIcon( QtWidgets.QMessageBox.Critical )
			error.setText( "Must enter a sample name" )
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

		self.Run_Measurment_Loop( sample_name, temperatures_to_measure, biases_to_measure )


	def Run_Measurment_Loop( self, sample_name, temperatures_to_measure, biases_to_measure ):
		for temperature in temperatures_to_measure:
			for bias in biases_to_measure:
				self.omnic_controller.Set_Response_Function(
					lambda ftir_file_contents :
					Deal_With_FTIR_Data( ftir_file_contents, self.sql_conn,
							sample_name, temperature, bias ) )

				if( temperature ): # None is ok, just means we don't know the temperature
					self.temp_controller.Set_Temperature_In_K( temperature )
					self.temp_controller.Turn_On()

					while( not self.temp_controller.Temperature_Is_Stable() ):
						QtCore.QCoreApplication.processEvents()
					print( "Temperature stable around: " + str(temperature) + '\n' )

				print( "Starting Measurement\n" )
				self.omnic_controller.Measure_Background( sample_name )

				while( not self.omnic_controller.Update() ):
					QtCore.QCoreApplication.processEvents()

		self.Turn_Off_Temp()
		self.omnic_controller.Set_Response_Function(
			lambda ftir_file_contents : None )

		print( "Finished Measurment\n" )




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

def Deal_With_FTIR_Data( ftir_file_contents, sql_conn, sample_name, temperature_in_k, bias_in_v ):
	#output_command_file = open( './test_auto.csv', 'w' )
	#output_command_file.write( file_contents )
	#output_command_file.close()

	wave_number = []
	intensity = []
	for line in ftir_file_contents.split('\n'):
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


if __name__ == "__main__":
	app = QtWidgets.QApplication(sys.argv)
	window = MyApp()
	window.show()
	sys.exit(app.exec_())

