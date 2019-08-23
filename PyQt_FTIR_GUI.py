if __name__ == "__main__": # This allows running this module by running this script
	import sys
	sys.path.insert(0, "..")

from PyQt5 import QtNetwork, QtCore, QtGui, uic, QtWidgets
import os
import sys

#import hashlib
from datetime import datetime
import re
import numpy as np
import configparser
import time

from FTIR_Commander.Omnic_Controller import Omnic_Controller
from FTIR_Commander.Graph import Graph

from MPL_Shared.Temperature_Controller import Temperature_Controller
from MPL_Shared.SQL_Controller import Commit_XY_Data_To_SQL, Connect_To_SQL
from MPL_Shared.Temperature_Controller_Settings import TemperatureControllerSettingsWindow

__version__ = '1.00'

base_path = os.path.dirname( os.path.realpath(__file__) )

def resource_path(relative_path = ""):  # Define function to import external files when using PyInstaller.
    """ Get absolute path to resource, works for dev and for PyInstaller """
    return os.path.join(base_path, relative_path)


qtCreatorFile = resource_path( "PyQt_FTIR_GUI.ui" ) # GUI layout file.

Ui_MainWindow, QtBaseClass = uic.loadUiType(qtCreatorFile)

def toFloatOrNone( as_string ):
	try:
		return float( as_string )
	except:
		return None



class FtirCommanderWindow(QtWidgets.QWidget, Ui_MainWindow):

	Set_New_Temperature_K = QtCore.pyqtSignal(float)
	Turn_Heater_Off = QtCore.pyqtSignal()
	#Turn_Off_Temperature_Control = QtCore.pyqtSignal(float)
	def __init__(self, parent=None, root_window=None):
		QtWidgets.QWidget.__init__(self, parent)
		Ui_MainWindow.__init__(self)
		self.setupUi(self)

		self.config_window = TemperatureControllerSettingsWindow()

		self.Init_Subsystems()
		self.Connect_Control_Logic()
		self.temp_controller_thread.start()
		self.omnic_controller_thread.start()

		self.temperature_graph.set_title("Measured Temperature Next To Sample")
		self.temperature_graph.setContentsMargins(0, 0, 0, 0)

	def PID_Coefficients_Updated( self, pid_coefficients ):
		pass



	def Init_Subsystems( self ):
		#Create_Table_If_Needed( self.sql_conn, self.sql_type )
		self.active_measurement_thread = None

		self.temp_controller = Temperature_Controller( resource_path( "configuration.ini" ) )
		self.temp_controller_thread = QtCore.QThread()
		self.temp_controller.moveToThread( self.temp_controller_thread )
		self.temp_controller_thread.started.connect( self.temp_controller.thread_start )

		self.omnic_controller = Omnic_Controller( resource_path( "configuration.ini" ) )
		self.omnic_controller_thread = QtCore.QThread()
		self.omnic_controller.moveToThread( self.omnic_controller_thread )
		self.omnic_controller_thread.started.connect( self.omnic_controller.thread_start )

		self.Temp_Controller_Disconnected() # Initialize temperature controller to disconnected
		self.Stop_Set_Temperature() # Initialize all heater settings to be off
		self.Omnic_Disconnected() # Initialize omnic controller to disconnected

		# Update labels on connection and disconnection to wifi devices
		self.temp_controller.Device_Connected.connect( self.Temp_Controller_Connected )
		self.temp_controller.Device_Disconnected.connect( self.Temp_Controller_Disconnected )
		self.omnic_controller.Device_Connected.connect( self.Omnic_Connected )
		self.omnic_controller.Device_Disconnected.connect( self.Omnic_Disconnected )

		# Run Connection to IV measurement system in another thread
		#self.iv_controller = IV_Controller()
		#self.iv_controller_thread = QtCore.QThread()
		#self.iv_controller.moveToThread( self.iv_controller_thread )
		#self.iv_controller_thread.started.connect( self.iv_controller.run )

		#self.iv_controller_thread.start()

		config = configparser.ConfigParser()
		config.read( resource_path( "configuration.ini" ) )
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

	def Open_Config_Window( self ):
		self.config_window.show()
		getattr(self.config_window, "raise")()
		self.config_window.activateWindow()


	def Connect_Control_Logic( self ):
		self.Stop_Measurment()
		#self.run_pushButton.clicked.connect( self.Start_Measurement )

		#random_noise_timer = QtCore.QTimer( self )
		#random_noise_timer.timeout.connect( lambda : self.Temperature_Update(numpy.random.uniform(low=280, high=300)) )
		#random_noise_timer.start( 500 )

		self.temp_controller.Temperature_Changed.connect( lambda temperature : self.temperature_graph.add_new_data_point( QtCore.QDateTime.currentDateTime(), temperature ) )
		self.temp_controller.Temperature_Changed.connect( lambda temperature : self.currentTemperature_lineEdit_2.setText( '{:.2f} K'.format( temperature ) ) )
		self.temp_controller.PID_Output_Changed.connect( lambda pid_output : self.temperature_graph.add_new_pid_output_data_point( QtCore.QDateTime.currentDateTime(), pid_output ) )
		self.temp_controller.PID_Output_Changed.connect( lambda pid_output : self.outputPower_lineEdit.setText( '{:.2f} %'.format( pid_output ) ) )
		self.temp_controller.Setpoint_Changed.connect( lambda setpoint : self.setpoint_lineEdit.setText( '{:.2f} K'.format( setpoint ) ) )

		self.config_window.Connect_Functions( self.temp_controller )
		self.settings_pushButton.clicked.connect( self.Open_Config_Window )


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

		self.Stop_Set_Temperature()
#		self.omnic_controller.Request_Settings( resource_path() )

		self.active_measurement =  Measurment_Loop( sample_name, user, temperatures_to_measure, biases_to_measure )
		self.active_measurement_thread = QtCore.QThread()
		self.active_measurement.moveToThread( self.active_measurement_thread )
		self.active_measurement_thread.started.connect( self.omnic_controller.Request_Settings )
		#self.active_measurement_thread.started.connect( self.active_measurement.Run )
		self.omnic_controller.Settings_File_Recieved.connect( self.active_measurement.Run )
		self.active_measurement.Temperature_Change_Requested.connect( self.temperature_graph.Temperature_Setpoint_Changed )
		self.active_measurement.Temperature_Change_Requested.connect( self.temp_controller.Set_Temp_And_Turn_On )
		self.Set_New_Temperature_K.connect( self.temp_controller.Set_Temp_And_Turn_On )
		self.active_measurement.Measurement_Begin.connect( self.omnic_controller.Measure_Sample )
		self.active_measurement.Finished.connect( self.active_measurement_thread.quit )
		self.temp_controller.Temperature_Stable.connect( self.active_measurement.Temperature_Ready )
		self.omnic_controller.File_Recieved.connect( self.active_measurement.Data_Gathered )
		self.active_measurement_thread.finished.connect( self.Stop_Measurment )
		self.active_measurement_thread.finished.connect( self.temp_controller.Turn_Off )


		try: self.run_pushButton.clicked.disconnect()
		except Exception: pass
		self.run_pushButton.setText( "Stop Measurement" )
		self.run_pushButton.setStyleSheet("QPushButton { background-color: rgba(255,0,0,255); color: rgba(0, 0, 0,255); }")
		self.run_pushButton.clicked.connect( self.active_measurement.Quit_Early )

		self.active_measurement_thread.start()

	def Stop_Measurment( self ):
		self.temperature_graph.Temperature_Setpoint_Changed( None )

		try: self.run_pushButton.clicked.disconnect() 
		except Exception: pass	
		self.run_pushButton.setText( "Run Sweep" )
		self.run_pushButton.setStyleSheet("QPushButton { background-color: rgba(0,255,0,255); color: rgba(0, 0, 0,255); }")
		self.run_pushButton.clicked.connect( self.Start_Measurement )

	def Start_Set_Temperature( self, temperature ):
		if temperature is None or ( self.active_measurement_thread is not None and self.active_measurement_thread.isRunning() ):
			return
		self.temperature_graph.Temperature_Setpoint_Changed( temperature )
		self.Set_New_Temperature_K.emit( temperature )
		self.setTemperature_pushButton.setText( "Stop Temperature" )
		self.setTemperature_pushButton.setStyleSheet("QPushButton { background-color: rgba(0,255,0,255); color: rgba(0, 0, 0,255); }")
		try: self.setTemperature_pushButton.clicked.disconnect() 
		except Exception: pass
		self.setTemperature_pushButton.clicked.connect( self.Stop_Set_Temperature )
		self.setTemperature_pushButton.clicked.connect( self.temp_controller.Turn_Off )

	def Stop_Set_Temperature( self ):
		self.temperature_graph.Temperature_Setpoint_Changed( None )

		self.setTemperature_pushButton.setText( "Hold Temperature" )
		self.setTemperature_pushButton.setStyleSheet("QPushButton { background-color: rgba(255,0,0,255); color: rgba(0, 0, 0,255); }")
		try: self.setTemperature_pushButton.clicked.disconnect() 
		except Exception: pass
		self.setTemperature_pushButton.clicked.connect( lambda : self.Start_Set_Temperature( toFloatOrNone(self.currentTemperature_lineEdit.text()) ) )
		#self.setTemperature_pushButton.clicked.connect( lambda : self.temp_controller.Set_Temp_And_Turn_On( toFloatOrNone(self.currentTemperature_lineEdit.text()) ) )


	def closeEvent( self, event ):
		self.run_pushButton.setText( "Closing" )
		QtWidgets.QWidget.closeEvent(self, event)


class Measurment_Loop( QtCore.QObject ):
	Finished = QtCore.pyqtSignal()
	Temperature_Change_Requested = QtCore.pyqtSignal( float )
	Measurement_Begin = QtCore.pyqtSignal()
	Finished = QtCore.pyqtSignal()

	def __init__( self, sample_name, user, temperatures_to_measure, biases_to_measure, parent=None ):
		super().__init__( parent )
		self.sample_name = sample_name
		self.user = user
		self.temperatures_to_measure = temperatures_to_measure
		self.biases_to_measure = biases_to_measure
		self.sql_type, self.sql_conn = Connect_To_SQL( resource_path( "configuration.ini" ) )

		self.temperature_ready = False
		self.data_gathered = False
		self.quit_early = False


	def Run( self ):
		for temperature in self.temperatures_to_measure:
			for bias in self.biases_to_measure:

				if temperature is not None: # None is ok, just means we don't care about setting the temperature
					self.Temperature_Change_Requested.emit( temperature )
					while( not self.temperature_ready ):
						if self.quit_early:
							self.Finished.emit()
							return
						time.sleep( 2 )
						QtCore.QCoreApplication.processEvents()
					self.temperature_ready = False

				print( "Starting Measurement\n" )
				self.temperature_in_k = temperature
				self.bias_in_v = bias
				self.Measurement_Begin.emit()

				while( not self.data_gathered ):
					if self.quit_early:
						self.Finished.emit()
						return
					time.sleep( 2 )
					QtCore.QCoreApplication.processEvents()
				self.data_gathered = False

		print( "Finished Measurment" )
		self.Finished.emit()

	def Temperature_Ready( self ):
		self.temperature_ready = True

	def Quit_Early( self ):
		print( "Quitting Early" )
		self.quit_early = True

	def Data_Gathered( self, file_name, ftir_file_contents, ftir_settings ):
		Deal_With_FTIR_Data( ftir_file_contents, self.user, self.sql_conn, self.sql_type,
					  self.sample_name, self.temperature_in_k, self.bias_in_v, ftir_settings )
		self.data_gathered = True

#def Create_Table_If_Needed( sql_conn, sql_type ):
#	cur = sql_conn.cursor()
#	try:
#		if sql_type == "QSQLITE":
#			cur.execute("""CREATE TABLE `ftir_measurements` ( `sample_name`	TEXT NOT NULL, `time`	DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, `measurement_id`	TEXT NOT NULL, `temperature_in_k`	REAL, `bias_in_v`	REAL, `user`	TEXT, `detector`	TEXT, `beam_splitter`	TEXT, `start_wave_number`	REAL, `end_wave_number`	REAL, `number_of_scans`	INTEGER, `velocity`	REAL, `aperture`	REAL, `gain`	REAL );""")
#		else:
#			cur.execute("""CREATE TABLE `ftir_measurements` ( `sample_name`	TEXT NOT NULL, `time`	DATETIME NOT NULL, `measurement_id`	TEXT NOT NULL, `temperature_in_k`	REAL, `bias_in_v`	REAL, `user`	TEXT, `detector`	TEXT, `beam_splitter`	TEXT, `start_wave_number`	REAL, `end_wave_number`	REAL, `number_of_scans`	INTEGER, `velocity`	REAL, `aperture`	REAL, `gain`	REAL );""")
#	except (mysql.connector.Error, mysql.connector.Warning) as e:
#		pass
#		#print(e)
#	except:
#		pass # Will cause exception if they already exist, but that's fine since we are just trying to make sure they exist

#	try:
#		cur.execute("""CREATE TABLE `raw_ftir_data` ( `measurement_id` TEXT NOT NULL, `wavenumber` REAL NOT NULL, `intensity` REAL NOT NULL );""")
#	except:
#		pass # Will cause exception if they already exist, but that's fine since we are just trying to make sure they exist

#	cur.close()
#	return False

def Deal_With_FTIR_Data( ftir_file_contents, user, sql_conn, sql_type, sample_name, temperature_in_k, bias_in_v, settings ):
	wave_number = []
	intensity = []
	for line in re.split( '\n|\r', ftir_file_contents.decode('utf8', 'ignore') ):
		data_split = line.split(',')
		if len( data_split ) < 2:
			continue
		wave_number.append( float(data_split[0]) )
		intensity.append( float(data_split[1]) )


	#m = hashlib.sha256()
	##m.update( 'Test'.encode() )
	#m.update( (sample_name + str( datetime.now() ) + ','.join(intensity) ).encode() )
	#measurement_id = m.hexdigest()
	if temperature_in_k is not None:
		temperature_in_k = str( temperature_in_k )

	meta_data_sql_entries = dict( sample_name=sample_name, user=user, temperature_in_k=temperature_in_k, bias_in_v=bias_in_v,
				 detector=settings["Detector"], beam_splitter=settings["Beam Splitter"], start_wave_number=settings["Start Wave Number"],
				 end_wave_number=settings["End Wave Number"], number_of_scans=settings["Number of Scans"], velocity=settings["Velocity"],
				 aperture=settings["Aperture"], gain=settings["Gain"] )

	Commit_XY_Data_To_SQL( sql_type, sql_conn, xy_data_sql_table="ftir_raw_data", xy_sql_labels=("wavenumber","intensity"),
					   x_data=wave_number, y_data=intensity, metadata_sql_table="ftir_measurements", **meta_data_sql_entries )

	print( "Data for temperature {} successfully committed".format( temperature_in_k ) )

if __name__ == "__main__":
	app = QtWidgets.QApplication(sys.argv)
	window = FtirCommanderWindow()
	window.show()
	#sys.exit(app.exec_())
	app.exec_()

