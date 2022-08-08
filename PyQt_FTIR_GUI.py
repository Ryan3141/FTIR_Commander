if __name__ == "__main__": # This allows running this module by running this script
	import pathlib
	import sys
	this_files_directory = pathlib.Path(__file__).parent.resolve()
	sys.path.insert(0, str(this_files_directory.parent.resolve()) ) # Add parent directory to access other modules

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QFileDialog
try:
	from PyQt5 import uic
except ImportError:
	import sip
import sys
import re
import numpy as np
import time
from threading import Event

from FTIR_Commander.Omnic_Controller import Omnic_Controller

from MPL_Shared.Temperature_Controller import Temperature_Controller
from MPL_Shared.Temperature_Controller_Settings import TemperatureControllerSettingsWindow
from MPL_Shared.SQL_Controller import Commit_XY_Data_To_SQL, Connect_To_SQL
from MPL_Shared.IV_Measurement_Assistant import IV_Controller
from MPL_Shared.Async_Iterator import Async_Iterator, Run_Async
from MPL_Shared.Saveable_Session import Saveable_Session

from MPL_Shared.Pad_Description_File import Get_Device_Description_File
from MPL_Shared.GUI_Tools import Popup_Error, Popup_Yes_Or_No, resource_path, Measurement_Sweep_Runner
from MPL_Shared.Threaded_Subsystems import Threaded_Subsystems

__version__ = '2.00'


Ui_MainWindow, QtBaseClass = uic.loadUiType( resource_path( "PyQt_FTIR_GUI.ui" ) ) # GUI layout file.



		#QMetaObject.invokeMethod( self.cv_controller, 'Voltage_Sweep', Qt.AutoConnection,
		#				  Q_RETURN_ARG('int'), Q_ARG(float, input_start), Q_ARG(float, input_end), Q_ARG(float, input_step) )
		#self.recent_results = (input_start = -1, input_end = 1, input_step = 0.01)


class FtirCommanderWindow( QtWidgets.QWidget, Ui_MainWindow, Saveable_Session, Threaded_Subsystems ):

	def __init__(self, parent=None, root_window=None):
		QtWidgets.QWidget.__init__(self, parent)
		Ui_MainWindow.__init__(self)
		self.setupUi(self)

		Saveable_Session.__init__( self, text_boxes = [(self.user_lineEdit, "user"),(self.descriptionFilePath_lineEdit, "pad_description_path"),(self.sampleName_lineEdit, "sample_name"),
					   (self.startVoltage_lineEdit, "start_v"),(self.endVoltage_lineEdit, "end_v"), (self.stepVoltage_lineEdit, "step_v"),
					   (self.startTemp_lineEdit, "start_T"),(self.endTemp_lineEdit, "end_T"), (self.stepTemp_lineEdit, "step_T")] )

		self.Init_Subsystems()
		self.Connect_Control_Logic()
		self.Start_Subsystems()

		self.Restore_Session( resource_path( "session.ini" ) )

	def closeEvent( self, event ):
		if self.measurement:
			self.quit_early.set()
			self.measurement.wait()
		Threaded_Subsystems.closeEvent(self, event)
		QtWidgets.QWidget.closeEvent(self, event)

	def Init_Subsystems( self ):
		self.config_window = TemperatureControllerSettingsWindow()
		self.measurement = None

		self.quit_early = Event()
		# self.status_layout = QHBoxLayout()
		# self.connectionsStatusDisplay_widget.setLayout( self.status_layout )
		# self.status_layout = QVBoxLayout( self.connectionsStatusDisplay_widget )
		status_layout = self.connectionsStatusDisplay_widget.layout()
		subsystems = self.Make_Subsystems( self, status_layout,
		                                   IV_Controller( machine_type="Keysight" ),
		                                   Temperature_Controller( resource_path( "configuration.ini" ) ),
		                                   Omnic_Controller( resource_path( "configuration.ini" ) ) )
		self.iv_controller, self.temp_controller, self.omnic_controller = subsystems

		self.iv_controller.Error_signal.connect( self.Error_During_Measurement )
		self.temperatureHold_widget.Connect_To_Temperature_Controller( self.temp_controller )

		self.temperature_graph.set_title("Measured Temperature Next To Sample")
		self.temperature_graph.setContentsMargins(0, 0, 0, 0)


	def Open_Config_Window( self ):
		self.config_window.show()
		getattr(self.config_window, "raise")()
		self.config_window.activateWindow()


	def Connect_Control_Logic( self ):
		self.Stop_Measurement()

		#random_noise_timer = QtCore.QTimer( self )
		#random_noise_timer.timeout.connect( lambda : self.Temperature_Update(numpy.random.uniform(low=280, high=300)) )
		#random_noise_timer.start( 500 )

		self.config_window.Connect_Functions( self.temp_controller )
		self.settings_pushButton.clicked.connect( self.Open_Config_Window )
		self.loadDevicesFile_pushButton.clicked.connect( self.Select_Device_File )
		self.temp_controller.Temperature_Changed.connect( lambda temperature : self.temperature_graph.add_new_data_point( QtCore.QDateTime.currentDateTime(), temperature ) )
		self.temp_controller.Temperature_Changed.connect( lambda temperature : self.currentTemperature_lineEdit_2.setText( f'{temperature:.2f} K' ) )
		self.temp_controller.PID_Output_Changed.connect( lambda pid_output : self.temperature_graph.add_new_pid_output_data_point( QtCore.QDateTime.currentDateTime(), pid_output ) )
		self.temp_controller.PID_Output_Changed.connect( lambda pid_output : self.outputPower_lineEdit.setText( f'{pid_output:.2f} %' ) )
		self.temp_controller.Setpoint_Changed.connect( lambda setpoint : self.setpoint_lineEdit.setText( f'{setpoint:.2f} K' ) )
		self.temp_controller.Setpoint_Changed.connect( self.temperature_graph.Temperature_Setpoint_Changed )
		self.temp_controller.Case_Temperature_Changed.connect( lambda t : self.caseTemperature_lineEdit.setText(f"{t:0.2f}") )

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

		input_to_values = lambda check_box, *text_boxes, append=[] : None if not check_box.isChecked() else ([ float(x.text()) for x in text_boxes ] + append)
		try:
			time_interval = 10E-3
			temperature_info = input_to_values(self.temp_checkBox, self.startTemp_lineEdit, self.endTemp_lineEdit, self.stepTemp_lineEdit)
			voltage_sweep_info = input_to_values(self.voltage_checkBox, self.startVoltage_lineEdit, self.endVoltage_lineEdit, self.stepVoltage_lineEdit, append=[time_interval])
		except ValueError:
			raise ValueError( "Invalid arguement for temperature or voltage range" )

		device_config_data = None if not self.runDevices_checkBox.isChecked() else Get_Device_Description_File( self.descriptionFilePath_lineEdit.text() )

		self.sql_type, self.sql_conn = Connect_To_SQL( resource_path( "configuration.ini" ) )
		meta_data = dict( sample_name=sample_name, user=user )

		return meta_data, temperature_info, voltage_sweep_info, device_config_data

	def Error_During_Measurement( self, error ):
		self.quit_early.set()
		self.Make_Safe()
		Popup_Error( "Error During Measurement:", error )

	def Start_Measurement( self ):
		try:
			self.Save_Session( resource_path( "session.ini" ) )
			self.quit_early.clear()
			self.measurement = Measurement_Sweep_Runner( self, self.Stop_Measurement, self.quit_early, Measurement_Sweep,
							                             self.temp_controller, self.iv_controller, self.omnic_controller,
							                             *self.Get_Measurement_Sweep_User_Input() )
		except Exception as e:
			Popup_Error( "Error Starting Measurement", str(e) )
			return

		# Update button to reuse it for stopping measurement
		try: self.run_pushButton.clicked.disconnect()
		except Exception: pass
		self.run_pushButton.setText( "Stop Measurement" )
		self.run_pushButton.setStyleSheet("QPushButton { background-color: rgba(255,0,0,255); color: rgba(0, 0, 0,255); }")
		self.run_pushButton.clicked.connect( self.Stop_Measurement )


	def Stop_Measurement( self ):
		self.quit_early.set()

		try: self.run_pushButton.clicked.disconnect()
		except Exception: pass
		self.run_pushButton.setText( "Run Sweep" )
		self.run_pushButton.setStyleSheet("QPushButton { background-color: rgba(0,255,0,255); color: rgba(0, 0, 0,255); }")
		self.run_pushButton.clicked.connect( self.Start_Measurement )


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


def Measurement_Sweep( quit_early,
                       temp_controller, iv_controller, omnic_controller,
					   meta_data, temperature_info, voltage_sweep_info, device_config_data ):

	sql_type, sql_conn = Connect_To_SQL( resource_path( "configuration.ini" ) )

	if device_config_data is None:
		run_devices = [None]

	else:
		run_devices  = Async_Iterator( device_config_data,
									   temp_controller, lambda current_device, temp_controller=temp_controller :
											temp_controller.Set_Active_Pads( current_device.neg_pad, current_device.pos_pad ),
									   temp_controller.Pads_Selected_Changed,
									   quit_early )
	if device_config_data is None or temperature_info is None:
		turn_off_heater = [None]
		turn_heater_back_on = [None]
	else:
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

	iv_meta_data = { "measurement_setup":"LN2 Dewar" }
	if temperature_info is None:
		run_temperatures = [None]
	else:
		temp_start, temp_end, temp_step = temperature_info
		run_temperatures = Async_Iterator( np.arange( temp_start, temp_end + temp_step / 2, temp_step ),
										   temp_controller, temp_controller.Set_Temp_And_Turn_On,
										   temp_controller.Temperature_Stable,
										   quit_early )

	if device_config_data is None:
		get_iv_results = [None]
	else:
		iv_meta_data.update( meta_data )
		get_iv_results = Async_Iterator( [None],
		                              iv_controller, lambda *args, v_start=-1.0, v_end=1.0, v_step=0.05, time_interval=0.05 :
		                                                    iv_controller.Voltage_Sweep( v_start, v_end, v_step, time_interval ),
		                              iv_controller.sweepFinished_signal,
		                              quit_early )

	get_omnic_settings = Async_Iterator( [None],
										 omnic_controller, lambda _ : omnic_controller.Request_Settings(),
										 omnic_controller.Settings_File_Recieved,
										 quit_early )

	get_results = Async_Iterator( [None],
								  omnic_controller, lambda _ : omnic_controller.Measure_Sample(),
								  omnic_controller.File_Recieved,
								  quit_early )

	set_gain_to_10000 = Async_Iterator( [None],
								  temp_controller, lambda _ : temp_controller.Set_Transimpedance_Gain( 1000 ),
								  temp_controller.Transimpedance_Gain_Changed,
								  quit_early )

	set_gain_to_normal_iv = Async_Iterator( [None],
								  temp_controller, lambda _ : temp_controller.Set_Transimpedance_Gain( 0 ),
								  temp_controller.Transimpedance_Gain_Changed,
								  quit_early )

	for settings in get_omnic_settings:
		meta_data.update( dict( detector=settings["Detector"], beam_splitter=settings["Beam Splitter"], start_wave_number=settings["Start Wave Number"],
								end_wave_number=settings["End Wave Number"], number_of_scans=settings["Number of Scans"], velocity=settings["Velocity"],
								aperture=settings["Aperture"], gain=settings["Gain"], dewar_temp_in_c=temp_controller.case_temperature ) )

	for temperature, device_info, voltage, _ in ((x,y,z,u) for x in run_temperatures for y in run_devices for z in run_voltages for u in turn_heater_back_on ):
		if temperature is not None:
			temperature = temperature[1]

		iv_meta_data["temperature_in_k"] = temperature
		meta_data["temperature_in_k"] = temperature
		pads_are_reversed = False
		if device_info is not None:
			device, pads_info = device_info
			(neg_pad, pos_pad), pads_are_reversed = pads_info
			iv_meta_data.update( dict( device_location=device.location, device_side_length_in_um=device.side ) )
			meta_data.update( dict( device_location=device.location, device_side_length_in_um=device.side ) )
			print( f"Starting Measurement for {device.location} side length {device.side} at {temperature} K on pads {neg_pad} and {pos_pad}" )

		if voltage is None:
			turn_on_bias = [None]
			meta_data["bias_in_v"] = None
		else:
			bias = -voltage if pads_are_reversed else voltage
			turn_on_bias = Async_Iterator( [None], iv_controller, lambda *args, bias=bias : iv_controller.Set_Bias( bias ), iv_controller.Bias_Is_Set, quit_early )
			meta_data.update( {"bias_in_v":voltage, "transimpedance_gain":1000} )

		if device_config_data is not None:
			for _, xy_data, _ in ((x,y,z) for z in set_gain_to_normal_iv for x in turn_off_heater for y in get_iv_results ):
				x_data, y_data = xy_data
				if pads_are_reversed:
					x_data = x_data[::-1]
					y_data = y_data[::-1]
				Commit_XY_Data_To_SQL( sql_type, sql_conn, xy_data_sql_table="iv_raw_data", xy_sql_labels=("voltage_v","current_a"),
									x_data=x_data, y_data=y_data, metadata_sql_table="iv_measurements", **iv_meta_data )
		for _, _, ftir_results, _ in ((x,y,z,u) for u in set_gain_to_10000 for x in turn_on_bias for y in turn_off_heater for z in get_results ):
			test = Run_Async( iv_controller, lambda : iv_controller.Make_Safe() ); test.Run()
			file_name, file_contents, ftir_settings = ftir_results
			wave_number, intensity = Deal_With_FTIR_Data( file_contents )

			Commit_XY_Data_To_SQL( sql_type, sql_conn, xy_data_sql_table="ftir_raw_data", xy_sql_labels=("wavenumber","intensity"),
			                       x_data=wave_number, y_data=intensity, metadata_sql_table="ftir_measurements", **meta_data )
			print( f"Data for temperature {temperature} successfully committed" )

	test1 = Run_Async( temp_controller, lambda : temp_controller.Make_Safe() ); test1.Run()
	test2 = Run_Async( iv_controller, lambda : iv_controller.Make_Safe() ); test2.Run()
	print( "Finished Measurment" )


if __name__ == "__main__":
	app = QtWidgets.QApplication( sys.argv )
	window = FtirCommanderWindow()
	window.show()
	#sys.exit( app.exec_() )
	app.exec_()
