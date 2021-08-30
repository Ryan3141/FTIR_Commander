if __name__ == "__main__": # This allows running this module by running this script
	import sys
	sys.path.insert(0, "..")

from PyQt5 import QtNetwork, QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QFileDialog
try:
	from PyQt5 import uic
except ImportError:
	import sip
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
from MPL_Shared.IV_Measurement_Assistant import IV_Controller
from MPL_Shared.Pad_Description_File import Get_Device_Description_File

import cProfile

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
	except ValueError:
		return None



class ProfiledThread(QtCore.QThread):
	pass
	## Overrides threading.Thread.run()
	#def run(self):
	#	profiler = cProfile.Profile()
	#	try:
	#		return profiler.runcall(QtCore.QThread.run, self)
	#	finally:
	#		profiler.dump_stats('myprofile-%d.profile' % (self.ident,))


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
		#self.temp_controller_thread = QtCore.QThread()
		self.temp_controller_thread = ProfiledThread()
		self.temp_controller.moveToThread( self.temp_controller_thread )
		self.temp_controller_thread.started.connect( self.temp_controller.thread_start )

		self.omnic_controller = Omnic_Controller( resource_path( "configuration.ini" ) )
		#self.omnic_controller_thread = QtCore.QThread()
		self.omnic_controller_thread = ProfiledThread()
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
		self.iv_controller = IV_Controller()
		self.iv_controller_thread = QtCore.QThread()
		self.iv_controller.moveToThread( self.iv_controller_thread )
		self.iv_controller_thread.started.connect( lambda : self.iv_controller.Initialize_Connection( "Keysight" ) )

		self.iv_controller_thread.start()

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
		self.temp_controller.Temperature_Changed.connect( lambda temperature : self.currentTemperature_lineEdit_2.setText( f'{temperature:.2f} K' ) )
		self.temp_controller.PID_Output_Changed.connect( lambda pid_output : self.temperature_graph.add_new_pid_output_data_point( QtCore.QDateTime.currentDateTime(), pid_output ) )
		self.temp_controller.PID_Output_Changed.connect( lambda pid_output : self.outputPower_lineEdit.setText( f'{pid_output:.2f} %' ) )
		self.temp_controller.Setpoint_Changed.connect( lambda setpoint : self.setpoint_lineEdit.setText( f'{setpoint:.2f} K' ) )
		self.temp_controller.Case_Temperature_Changed.connect( lambda t : self.caseTemperature_lineEdit.setText(f"{t:0.2f}") )
		self.Set_New_Temperature_K.connect( self.temp_controller.Set_Temp_And_Turn_On )
		self.Turn_Heater_Off.connect( self.temp_controller.Turn_Off )

		self.config_window.Connect_Functions( self.temp_controller )
		self.settings_pushButton.clicked.connect( self.Open_Config_Window )
		self.loadDevicesFile_pushButton.clicked.connect( self.Select_Device_File )


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
			biases_to_measure = np.arange( v_start, v_end + v_step / 2, v_step )
		else:
			biases_to_measure = [None]

		if( self.runDevices_checkBox.isChecked() ):
			device_info = Get_Device_Description_File( self.deviceFile_lineEdit.text() )
		else:
			device_info = None
		#self.Stop_Set_Temperature()
#		self.omnic_controller.Request_Settings( resource_path() )

		self.active_measurement =  Measurment_Loop( sample_name, user, temperatures_to_measure, biases_to_measure, device_info )
		self.active_measurement_thread = QtCore.QThread()
		self.active_measurement.moveToThread( self.active_measurement_thread )
		self.active_measurement_thread.started.connect( self.omnic_controller.Request_Settings )
		#self.active_measurement_thread.started.connect( self.active_measurement.Run )

		# Connect interactions with iv measurments and temperature control
		self.active_measurement.shutoffTemp_signal.connect( self.temp_controller.Turn_Off )
		self.active_measurement.turnonTemp_signal.connect( self.temp_controller.Turn_On )
		self.omnic_controller.Settings_File_Recieved.connect( self.active_measurement.Run )
		self.omnic_controller.Settings_File_Recieved.connect( self.Maintain_Temp_Stop_Set_Temperature )
		self.active_measurement.Temperature_Change_Requested.connect( self.temperature_graph.Temperature_Setpoint_Changed )
		self.active_measurement.Temperature_Change_Requested.connect( self.temp_controller.Set_Temp_And_Turn_On )
		self.active_measurement.Measurement_Begin.connect( self.omnic_controller.Measure_Sample )
		self.active_measurement.Finished.connect( self.active_measurement_thread.quit )
		self.temp_controller.Temperature_Stable.connect( self.active_measurement.Temperature_Ready )
		self.temp_controller.Case_Temperature_Changed.connect( self.active_measurement.Case_Temperature_Changed )
		self.omnic_controller.File_Recieved.connect( self.active_measurement.Data_Gathered )
		self.active_measurement_thread.finished.connect( self.Stop_Measurment )
		self.active_measurement_thread.finished.connect( self.temp_controller.Turn_Off )
		self.iv_controller.Bias_Is_Set.connect( lambda voltage, current : self.active_measurement.Bias_Ready() )
		self.active_measurement.changeBias_Requested.connect( self.iv_controller.Set_Bias )
		self.active_measurement.stopBias_Requested.connect( self.iv_controller.Turn_Off_Bias )
		self.active_measurement.Finished.connect( self.iv_controller.Turn_Off_Bias )
		self.temp_controller.Pads_Selected_Changed.connect( self.active_measurement.Pads_Ready )
		self.active_measurement.Pad_Change_Requested.connect( self.temp_controller.Set_Active_Pads )


		try: self.run_pushButton.clicked.disconnect()
		except Exception: pass
		self.run_pushButton.setText( "Stop Measurement" )
		self.run_pushButton.setStyleSheet("QPushButton { background-color: rgba(255,0,0,255); color: rgba(0, 0, 0,255); }")
		self.run_pushButton.clicked.connect( self.active_measurement.Quit_Early )

		self.active_measurement_thread.start()

	def Stop_Measurment( self ):
		self.temperature_graph.Temperature_Setpoint_Changed( None )
		self.Turn_Heater_Off.emit()

		try: self.run_pushButton.clicked.disconnect()
		except Exception: pass
		self.run_pushButton.setText( "Run Sweep" )
		self.run_pushButton.setStyleSheet("QPushButton { background-color: rgba(0,255,0,255); color: rgba(0, 0, 0,255); }")
		self.run_pushButton.clicked.connect( self.Start_Measurement )

	def Start_Set_Temperature( self, temperature ):
		if temperature is None or ( self.active_measurement_thread is not None and self.active_measurement_thread.isRunning() ):
			return
		self.temperature_graph.Temperature_Setpoint_Changed( temperature )
		self.Set_New_Temperature_K.emit( float(temperature) )
		self.setTemperature_pushButton.setText( "Stop Temperature" )
		self.setTemperature_pushButton.setStyleSheet("QPushButton { background-color: rgba(0,255,0,255); color: rgba(0, 0, 0,255); }")
		try: self.setTemperature_pushButton.clicked.disconnect()
		except Exception: pass
		self.setTemperature_pushButton.clicked.connect( self.Stop_Set_Temperature )
		self.setTemperature_pushButton.clicked.connect( self.temp_controller.Turn_Off )

	def Stop_Set_Temperature( self ):
		self.temperature_graph.Temperature_Setpoint_Changed( None )
		self.Turn_Heater_Off.emit()

		self.setTemperature_pushButton.setText( "Hold Temperature" )
		self.setTemperature_pushButton.setStyleSheet("QPushButton { background-color: rgba(255,0,0,255); color: rgba(0, 0, 0,255); }")
		try: self.setTemperature_pushButton.clicked.disconnect()
		except Exception: pass
		self.setTemperature_pushButton.clicked.connect( lambda : self.Start_Set_Temperature( toFloatOrNone(self.currentTemperature_lineEdit.text()) ) )
		#self.setTemperature_pushButton.clicked.connect( lambda : self.temp_controller.Set_Temp_And_Turn_On( toFloatOrNone(self.currentTemperature_lineEdit.text()) ) )

	def Maintain_Temp_Stop_Set_Temperature( self ):
		self.setTemperature_pushButton.setText( "Hold Temperature" )
		self.setTemperature_pushButton.setStyleSheet("QPushButton { background-color: rgba(255,0,0,255); color: rgba(0, 0, 0,255); }")
		try: self.setTemperature_pushButton.clicked.disconnect()
		except Exception: pass
		self.setTemperature_pushButton.clicked.connect( lambda : self.Start_Set_Temperature( toFloatOrNone(self.currentTemperature_lineEdit.text()) ) )

	def closeEvent( self, event ):
		self.run_pushButton.setText( "Closing" )
		QtWidgets.QWidget.closeEvent(self, event)

	def Select_Device_File( self ):
		fileName, _ = QFileDialog.getOpenFileName( self, "QFileDialog.getSaveFileName()", "", "CSV Files (*.csv);;All Files (*)" )
		if fileName == "": # User cancelled
			return
		config_info = Get_Device_Description_File( fileName )
		if config_info is None:
			return

		self.deviceFile_lineEdit.setText( fileName )


class Measurement_Plan:
	def __init__( self, ):
		pass

	def __iter__( self ):
		return self

	def __next__( self ):
		for temperature in self.temperatures_to_measure:
			for bias in self.biases_to_measure:
				yield (temperature, bias)

class Measurment_Loop( QtCore.QObject ):
	Temperature_Change_Requested = QtCore.pyqtSignal( float )
	Measurement_Begin = QtCore.pyqtSignal()
	Finished = QtCore.pyqtSignal()
	shutoffTemp_signal = QtCore.pyqtSignal()
	turnonTemp_signal = QtCore.pyqtSignal()
	changeBias_Requested = QtCore.pyqtSignal( float )
	stopBias_Requested = QtCore.pyqtSignal()
	Pad_Change_Requested = QtCore.pyqtSignal( int, int )

	def __init__( self, sample_name, user, temperatures_to_measure, biases_to_measure, device_config_data, parent=None ):
		super().__init__( parent )
		self.sample_name = sample_name
		self.user = user
		self.temperatures_to_measure = temperatures_to_measure
		self.case_temperature = None
		self.biases_to_measure = biases_to_measure

		self.temperature_ready = False
		self.pads_ready = False
		self.bias_ready = False
		self.data_gathered = False
		self.quit_early = False

		# device_config_data = Get_Device_Description_File( self.descriptionFilePath_lineEdit.text() )
		self.device_config_data = device_config_data

	def Wait_For_Temp_And_Pads( self ):
		while( not (self.temperature_ready and self.pads_ready) ):
			if self.quit_early:
				self.Finished.emit()
				return True
			time.sleep( 2 )
			QtCore.QCoreApplication.processEvents()
		self.temperature_ready = False
		self.pads_ready = False
		return False

	def Run( self ):
		self.sql_type, self.sql_conn = Connect_To_SQL( resource_path( "configuration.ini" ) )
		expected_data = ["Negative Pad","Positive Pad","Device Area (um^2)","Device Perimeter (um)", "Device Location"]
		if self.device_config_data is not None:
			number_of_devices = range( len(self.device_config_data["Negative Pad"]) )
		else:
			number_of_devices = [ None ]
		for temperature in self.temperatures_to_measure:
			for device_index in number_of_devices:
				if device_index is not None:
					neg_pad, pos_pad, area, perimeter, location = (self.device_config_data[key][device_index] for key in expected_data)
					self.device_meta_data = dict( device_side_length_in_um=area, device_location=location )
				else:
					neg_pad, pos_pad = 1, 2
					self.device_meta_data = {}
				for bias in self.biases_to_measure:

					if temperature is not None: # None is ok, just means we don't care about setting the temperature
						self.turnonTemp_signal.emit()
						self.Temperature_Change_Requested.emit( temperature )
						self.Pad_Change_Requested.emit( int(neg_pad), int(pos_pad) )
						if self.Wait_For_Temp_And_Pads():
							self.Finished.emit()
							return
					else:
						print( "No temperature set" )

					if bias is not None:
						self.changeBias_Requested.emit( bias )
						while( not self.bias_ready ):
							if self.quit_early:
								self.Finished.emit()
								return
							time.sleep( 2 )
							QtCore.QCoreApplication.processEvents()
						self.bias_ready = False
						self.shutoffTemp_signal.emit()

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
					self.stopBias_Requested.emit()
		print( "Finished Measurment" )
		self.Finished.emit()

	def Case_Temperature_Changed( self, temp_in_c ):
		self.case_temperature = temp_in_c

	def Pads_Ready( self, pads, is_reversed ):
		self.pads_ready = True
		self.pads_are_reversed = is_reversed

	def Temperature_Ready( self ):
		self.temperature_ready = True

	def Bias_Ready( self ):
		self.bias_ready = True

	def Quit_Early( self ):
		print( "Quitting Early" )
		self.quit_early = True

	def Data_Gathered( self, file_name, ftir_file_contents, ftir_settings ):
		Deal_With_FTIR_Data( ftir_file_contents, self.user, self.sql_conn, self.sql_type,
					  self.sample_name, self.temperature_in_k, self.case_temperature, self.bias_in_v, ftir_settings, self.device_meta_data )
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

def Deal_With_FTIR_Data( ftir_file_contents, user, sql_conn, sql_type, sample_name, temperature_in_k, case_temperature_in_c, bias_in_v, settings, device_meta_data ):
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
				 aperture=settings["Aperture"], gain=settings["Gain"], dewar_temp_in_c=case_temperature_in_c )
	meta_data_sql_entries.update( device_meta_data )
	Commit_XY_Data_To_SQL( sql_type, sql_conn, xy_data_sql_table="ftir_raw_data", xy_sql_labels=("wavenumber","intensity"),
					   x_data=wave_number, y_data=intensity, metadata_sql_table="ftir_measurements", **meta_data_sql_entries )

	print( "Data for temperature {} successfully committed".format( temperature_in_k ) )

if __name__ == "__main__":
	app = QtWidgets.QApplication(sys.argv)
	window = FtirCommanderWindow()
	window.show()
	#sys.exit(app.exec_())
	app.exec_()
	#cProfile.run('app.exec_()')
	pass
	#profiler = cProfile.Profile()
	#profiler.runcall(QtWidgets.QApplication.exec_, app)
	#profiler.dump_stats('myprofile-%d.profile' % (self.ident,))

