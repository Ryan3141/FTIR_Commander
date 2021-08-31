if __name__ == "__main__": # This allows running this module by running this script
	import pathlib
	import sys
	this_files_directory = pathlib.Path(__file__).parent.resolve()
	sys.path.insert(0, str(this_files_directory.parent.resolve()) ) # Add parent directory to access other modules

from PyQt5 import QtCore, QtGui, QtWidgets
try:
	from PyQt5 import uic
except ImportError:
	import sip
import os
import sys
from datetime import datetime
import re
import numpy as np
import time

from FTIR_Commander.Omnic_Controller import Omnic_Controller
from FTIR_Commander.Graph import Graph

from MPL_Shared.Temperature_Controller import Temperature_Controller
from MPL_Shared.Temperature_Controller_Settings import TemperatureControllerSettingsWindow
from MPL_Shared.SQL_Controller import Commit_XY_Data_To_SQL, Connect_To_SQL
from MPL_Shared.IV_Measurement_Assistant import IV_Controller
from MPL_Shared.Async_Iterator import Async_Iterator, Run_Async
from MPL_Shared.Saveable_Session import Saveable_Session
from itertools import product

from MPL_Shared.Pad_Description_File import Get_Device_Description_File

__version__ = '2.00'

base_path = os.path.dirname( os.path.realpath(__file__) )

def resource_path(relative_path = ""):  # Define function to import external files when using PyInstaller.
    """ Get absolute path to resource, works for dev and for PyInstaller """
    return os.path.join(base_path, relative_path)


Ui_MainWindow, QtBaseClass = uic.loadUiType( resource_path( "PyQt_FTIR_GUI.ui" ) ) # GUI layout file.

def toFloatOrNone( as_string ):
	try:
		return float( as_string )
	except ValueError:
		return None

def Popup_Error( title, message ):
	error = QtWidgets.QMessageBox()
	error.setIcon( QtWidgets.QMessageBox.Critical )
	error.setText( message )
	error.setWindowTitle( title )
	error.setStandardButtons( QtWidgets.QMessageBox.Ok )
	return_value = error.exec_()
	return


class FtirCommanderWindow(QtWidgets.QWidget, Ui_MainWindow, Saveable_Session):

	Set_New_Temperature_K = QtCore.pyqtSignal(float)
	Turn_Heater_Off = QtCore.pyqtSignal()
	#Turn_Off_Temperature_Control = QtCore.pyqtSignal(float)

	def __init__(self, parent=None, root_window=None):
		QtWidgets.QWidget.__init__(self, parent)
		Ui_MainWindow.__init__(self)
		self.setupUi(self)

		Saveable_Session.__init__( self, text_boxes = [(self.user_lineEdit, "user"),(self.descriptionFilePath_lineEdit, "pad_description_path"),(self.sampleName_lineEdit, "sample_name"),
					   (self.startVoltage_lineEdit, "start_v"),(self.endVoltage_lineEdit, "end_v"), (self.stepVoltage_lineEdit, "step_v"),
					   (self.startTemp_lineEdit, "start_T"),(self.endTemp_lineEdit, "end_T"), (self.stepTemp_lineEdit, "step_T")] )


		self.Init_Subsystems()
		self.Connect_Control_Logic()
		self.iv_controller_thread.start()
		self.temp_controller_thread.start()
		self.omnic_controller_thread.start()

		self.Restore_Session( resource_path( "session.ini" ) )

		self.temperature_graph.set_title("Measured Temperature Next To Sample")
		self.temperature_graph.setContentsMargins(0, 0, 0, 0)

	def closeEvent( self, event ):
		self.run_pushButton.setText( "Closing" )
		self.iv_controller_thread.quit()
		self.temp_controller_thread.quit()
		self.omnic_controller_thread.quit()
		QtWidgets.QWidget.closeEvent(self, event)

	def Init_Subsystems( self ):
		self.config_window = TemperatureControllerSettingsWindow()
		self.active_measurement_thread = None

		# Run Connection to IV measurement system in another thread
		self.iv_controller = IV_Controller()
		self.iv_controller_thread = QtCore.QThread( self )
		self.iv_controller.moveToThread( self.iv_controller_thread )
		self.iv_controller_thread.started.connect( lambda : self.iv_controller.Initialize_Connection( "Keysight" ) )

		self.temp_controller = Temperature_Controller( resource_path( "configuration.ini" ) )
		self.temp_controller_thread = QtCore.QThread( self )
		self.temp_controller.moveToThread( self.temp_controller_thread )
		self.temp_controller_thread.started.connect( self.temp_controller.thread_start )
		self.temp_controller_thread.finished.connect( self.temp_controller.thread_stop )

		self.omnic_controller = Omnic_Controller( resource_path( "configuration.ini" ) )
		self.omnic_controller_thread = QtCore.QThread( self )
		self.omnic_controller.moveToThread( self.omnic_controller_thread )
		self.omnic_controller_thread.started.connect( self.omnic_controller.thread_start )
		self.omnic_controller_thread.finished.connect( self.omnic_controller.thread_stop )

		self.Temp_Controller_Disconnected() # Initialize temperature controller to disconnected
		self.Stop_Set_Temperature() # Initialize all heater settings to be off
		self.Omnic_Disconnected() # Initialize omnic controller to disconnected

		# Update labels on connection and disconnection to wifi devices
		self.temp_controller.Device_Connected.connect( self.Temp_Controller_Connected )
		self.temp_controller.Device_Disconnected.connect( self.Temp_Controller_Disconnected )
		self.omnic_controller.Device_Connected.connect( self.Omnic_Connected )
		self.omnic_controller.Device_Disconnected.connect( self.Omnic_Disconnected )



	def Open_Config_Window( self ):
		self.config_window.show()
		getattr(self.config_window, "raise")()
		self.config_window.activateWindow()


	def Connect_Control_Logic( self ):
		self.Stop_Measurement()
		#self.run_pushButton.clicked.connect( self.Start_Measurement )

		#random_noise_timer = QtCore.QTimer( self )
		#random_noise_timer.timeout.connect( lambda : self.Temperature_Update(numpy.random.uniform(low=280, high=300)) )
		#random_noise_timer.start( 500 )


		self.config_window.Connect_Functions( self.temp_controller )
		self.settings_pushButton.clicked.connect( self.Open_Config_Window )
		self.temp_controller.Temperature_Changed.connect( lambda temperature : self.temperature_graph.add_new_data_point( QtCore.QDateTime.currentDateTime(), temperature ) )
		self.temp_controller.Temperature_Changed.connect( lambda temperature : self.currentTemperature_lineEdit_2.setText( f'{temperature:.2f} K' ) )
		self.temp_controller.PID_Output_Changed.connect( lambda pid_output : self.temperature_graph.add_new_pid_output_data_point( QtCore.QDateTime.currentDateTime(), pid_output ) )
		self.temp_controller.PID_Output_Changed.connect( lambda pid_output : self.outputPower_lineEdit.setText( f'{pid_output:.2f} %' ) )
		self.temp_controller.Setpoint_Changed.connect( lambda setpoint : self.setpoint_lineEdit.setText( f'{setpoint:.2f} K' ) )
		self.temp_controller.Case_Temperature_Changed.connect( lambda t : self.caseTemperature_lineEdit.setText(f"{t:0.2f}") )
		self.Set_New_Temperature_K.connect( self.temp_controller.Set_Temp_And_Turn_On )
		self.Turn_Heater_Off.connect( self.temp_controller.Turn_Off )


	def Select_Device_File( self ):
		fileName, _ = QFileDialog.getOpenFileName( self, "QFileDialog.getSaveFileName()", "", "CSV Files (*.csv);;All Files (*)" )
		if fileName == "": # User cancelled
			return
		try:
			config_info = Get_Device_Description_File( fileName )
		except Exception as e:
			Popup_Error( "Error", str(e) )
			return

		self.descriptionFilePath_lineEdit.setText( fileName )

	def Get_Measurement_Sweep_User_Input( self ):
		sample_name = self.sampleName_lineEdit.text()
		user = str( self.user_lineEdit.text() )
		if( sample_name == "" or user == "" ):
			raise ValueError( "Must enter a sample name and user" )

		try:
			temp_start, temp_end, temp_step = float(self.startTemp_lineEdit.text()), float(self.endTemp_lineEdit.text()), float(self.stepTemp_lineEdit.text())
			v_start, v_end, v_step = float(self.startVoltage_lineEdit.text()), float(self.endVoltage_lineEdit.text()), float(self.stepVoltage_lineEdit.text())
			time_interval = float( self.timeInterval_lineEdit.text() )
		except ValueError:
			raise ValueError( "Invalid arguement for temperature or voltage range" )

		device_config_data = Get_Device_Description_File( self.descriptionFilePath_lineEdit.text() )

		self.sql_type, self.sql_conn = Connect_To_SQL( resource_path( "configuration.ini" ) )
		meta_data = dict( sample_name=sample_name, user=user, measurement_setup="LN2 Dewar" )

		return meta_data, (temp_start, temp_end, temp_step), (v_start, v_end, v_step, time_interval), device_config_data

	def Start_Measurement( self ):
		try:
			self.Save_Session( resource_path( "session.ini" ) )
			self.measurement = Measurement_Sweep_Runner( self, self.Stop_Measurement,
			                   self.temp_controller, self.iv_controller, self.omnic_controller,
			                   *self.Get_Measurement_Sweep_User_Input(),
			                   quit_early=self.takeMeasurementSweep_pushButton.clicked )
		except Exception as e:
			Popup_Error( "Error Starting Measurement", str(e) )
			return

		# Update button to reuse it for stopping measurement
		try: self.run_pushButton.clicked.disconnect()
		except Exception: pass
		self.run_pushButton.setText( "Stop Measurement" )
		self.run_pushButton.setStyleSheet("QPushButton { background-color: rgba(255,0,0,255); color: rgba(0, 0, 0,255); }")


	def Stop_Measurement( self ):
		self.temperature_graph.Temperature_Setpoint_Changed( None )
		self.Turn_Heater_Off.emit()

		try: self.run_pushButton.clicked.disconnect()
		except Exception: pass
		self.run_pushButton.setText( "Run Sweep" )
		self.run_pushButton.setStyleSheet("QPushButton { background-color: rgba(0,255,0,255); color: rgba(0, 0, 0,255); }")
		self.run_pushButton.clicked.connect( self.Start_Measurement )

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


def Deal_With_FTIR_Data( ftir_file_contents ):
	wave_number = []
	intensity = []
	for line in re.split( '\n|\r', ftir_file_contents.decode('utf8', 'ignore') ):
		data_split = line.split(',')
		if len( data_split ) < 2:
			continue
		wave_number.append( float(data_split[0]) )
		intensity.append( float(data_split[1]) )

	return wave_number, intensity


class Measurement_Sweep_Runner( QtCore.QObject ):
	Finished_signal = QtCore.pyqtSignal()
	def __init__( self, parent, finished, *args, **kargs ):
		QtCore.QObject.__init__(self)
		self.Finished_signal.connect( finished )
		self.args = args
		self.kargs = kargs
		# self.Run()
		self.thead_to_use = QtCore.QThread( parent=parent )
		self.moveToThread( self.thead_to_use )
		self.thead_to_use.started.connect( self.Run )
		# self.thead_to_use.finished.connect( self.thead_to_use.deleteLater )
		self.thead_to_use.start()

	def Run( self ):
		Measurement_Sweep( *self.args, **self.kargs )
		self.Finished_signal.emit()

def Measurement_Sweep( temp_controller, iv_controller, omnic_controller,
                       meta_data, temperature_info, voltage_sweep_info, device_config_data,
                       quit_early ):
	sql_type, sql_conn = Connect_To_SQL( resource_path( "configuration.ini" ) )

	if device_config_data is None:
		run_devices = [None]
		turn_off_heater = [None]
		turn_heater_back_on = [None]

	else:
		run_devices  = Async_Iterator( device_config_data,
		                               temp_controller.Set_Active_Pads,
		                               lambda current_device, temp_controller=temp_controller :
		                                      temp_controller.Set_Active_Pads( current_device.neg_pad, current_device.pos_pad ),
		                               temp_controller.Pads_Selected_Changed,
		                               quit_early )
		turn_off_heater = Async_Iterator( [None],
		                                  temp_controller, lambda _ : temp_controller.Turn_Off(),
		                                  temp_controller.Heater_Output_Off,
		                                  quit_early )
		turn_heater_back_on = Async_Iterator( [None],
		                                      temp_controller, lambda _ : temp_controller.Turn_On(),
		                                      temp_controller.Temperature_Stable,
		                                      quit_early )

	if voltage_sweep_info is None:
		run_voltages = [None]
	else:
		v_start, v_end, v_step, time_interval = voltage_sweep_info
		run_voltages = np.arange( v_start, v_end + v_step / 2, v_step )


	if temperature_info is None:
		run_temperatures = [None]
	else:
		temp_start, temp_end, temp_step = temperature_info
		run_temperatures = Async_Iterator( np.arange( temp_start, temp_end + temp_step / 2, temp_step ),
		                                   temp_controller, temp_controller.Set_Temp_And_Turn_On,
		                                   temp_controller.Temperature_Stable,
		                                   quit_early )
	get_omnic_settings = Async_Iterator( [None],
	                                     omnic_controller.Request_Settings,
	                                     omnic_controller.Settings_File_Recieved,
	                                     quit_early )

	get_results = Async_Iterator( [None],
	                              omnic_controller.Measure_Sample,
	                              omnic_controller.Settings_File_Recieved,
	                              quit_early )

	for settings in get_omnic_settings:
		meta_data.update( dict( detector=settings["Detector"], beam_splitter=settings["Beam Splitter"], start_wave_number=settings["Start Wave Number"],
		                        end_wave_number=settings["End Wave Number"], number_of_scans=settings["Number of Scans"], velocity=settings["Velocity"],
		                        aperture=settings["Aperture"], gain=settings["Gain"], dewar_temp_in_c=case_temperature_in_c ) )

	for temperature, (device, pads_info), voltage, _ in ((x,y,z,u) for x in run_temperatures for y in run_devices for z in run_voltages for u in turn_heater_back_on ):
		meta_data.update( dict( temperature_in_k=temperature, device_location=device.location, device_side_length_in_um=device.side ) )
		(neg_pad, pos_pad), pads_are_reversed = pads_info
		print( f"Starting Measurement for {device.location} side length {device.side} at {temperature} K on pads {neg_pad} and {pos_pad}" )
		if voltage is None:
			if pads_are_reversed:
				voltage = -voltage
			turn_on_bias = Async_Iterator( [None], lambda *args, bias=voltage : temp_controller.Set_Bias( bias ), iv_controller.Bias_Is_Set )
			meta_data["bias_in_v"] = voltage
		else:
			turn_on_bias = [None]
			meta_data["bias_in_v"] = None

		for _, _, ftir_file_contents in ((x,y,z) for x in turn_on_bias for y in turn_off_heater for z in get_results ):
			wave_number, intensity = Deal_With_FTIR_Data( ftir_file_contents )

#			Commit_XY_Data_To_SQL( sql_type, sql_conn, xy_data_sql_table="ftir_raw_data", xy_sql_labels=("wavenumber","intensity"),
#			                       x_data=wave_number, y_data=intensity, metadata_sql_table="ftir_measurements", **meta_data )
			print( f"Data for temperature {temperature} successfully committed" )

	print( "Finished Measurment" )


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

