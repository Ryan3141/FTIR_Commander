import time
import tkinter as tk
from tkinter import messagebox
import matplotlib.pyplot as plt
import numpy as np

from FTIR_Commander import ftir_application

class FTIR_GUI:
	def __init__(self, master):
		self.master = master
		self.master.columnconfigure(0, weight=1)
		self.master.rowconfigure(0, weight=1)
		row_for_meta_data = 0
		self.name_entry = self.Custom_Entry( "Sample Name", "", 1, row_for_meta_data, columnspan=3 )

		row_for_temps = row_for_meta_data + 2
		self.temperature_control_toggle = tk.BooleanVar()
		self.temperature_control_toggle.set( True )
		tk.Checkbutton(self.master, text="", variable=self.temperature_control_toggle).grid(row=row_for_temps, sticky='w')
		self.low_temperature = self.Custom_Entry( "Lower Temperature (K)", "295", 1, row_for_temps )
		self.high_temperature = self.Custom_Entry( "Upper Temperature (K)", "305", 2, row_for_temps )
		self.step_temperature = self.Custom_Entry( "Temperature Step (K)", "5", 3, row_for_temps )

		row_for_biases = row_for_temps + 2
		self.bias_control_toggle = tk.BooleanVar()
		self.bias_control_toggle.set( True )
		tk.Checkbutton(self.master, text="", variable=self.bias_control_toggle).grid(row=row_for_biases, sticky='w')
		self.low_bias = self.Custom_Entry( "Lower Voltage (V)", "-0.1", 1, row_for_biases )
		self.high_bias = self.Custom_Entry( "Upper Voltage (V)", "0.1", 2, row_for_biases )
		self.step_bias = self.Custom_Entry( "Voltage Step (V)", "0.01", 3, row_for_biases )

		row_for_button = row_for_biases + 2
		self.run_measurment = tk.Button(master, text="Start Measurement", command=self.Start_Measurement)
		self.run_measurment.grid(row=row_for_button,column=2, sticky='s,w', padx=5, pady=5)

		try:
			#self.app = ftir_application( directory_for_commands=r"\\NICCOMP\ExportData\Commands", directory_for_results=r"\\NICCOMP\ExportData\Output" )
			self.app = ftir_application( directory_for_commands=r"C:\Users\Ryan\Documents\Visual Studio 2017\Projects\FTIR_Commander\FTIR_Commander\Commands",
							   directory_for_results=r"C:\Users\Ryan\Documents\Visual Studio 2017\Projects\FTIR_Commander\FTIR_Commander\Outputs" )
			self.Display_Temperature()
		except Exception as err:
			messagebox.showerror( "Error", err )

		#self.after(500, self.Update_Temperature)

	# Basic structure to set up gui in a cleaner manner
	def Custom_Entry( self, title, default_value, column, start_row, columnspan=1 ):
		the_label = tk.Label(self.master, height=1, width=20, text=title, bg="white")
		the_label.grid(row=start_row, column=column, rowspan=1, padx=1, pady=1)
		the_entry = tk.Entry(self.master, width=10)
		the_entry.grid(row=start_row + 1,column=column, columnspan=columnspan, padx=5, pady=5, sticky='s,w,e,n')
		the_entry.insert( tk.INSERT, default_value )
		return the_entry

	def Display_Temperature( self ): # Open a graph to plot the temperature over time
		plt.ion()

		self.temperature_data = []
		self.temperature_data_times = []
		fig = plt.figure()
		self.ax = fig.add_subplot(111)
		plt.xlabel('Time (s)')
		plt.ylabel('Temperature (K)')
		plt.title('Temperature Under the Sample')
		plt.grid(True)
		self.temperature_graph, = plt.plot([],[],'r-')
		self.start_time = time.time()
		self.master.after(1, self.Update_Temperature )

	def Update_Temperature( self ):
		#line1, = ax.plot(x, y, 'r-') # Returns a tuple of line objects, thus the comma
		the_time = time.time() - self.start_time
		self.app.temp_controller.Update()
		temperature = self.app.temp_controller.Get_Temperature_In_K()
		if( not temperature ):
			self.master.after(500, self.Update_Temperature)
			return

		self.temperature_data_times.append( the_time )
		self.temperature_data.append( temperature )

		# Only show the last 60 samples taken
		if( len(self.temperature_data_times) > 60 ):
			self.temperature_data_times = self.temperature_data_times[-60:]
			self.temperature_data = self.temperature_data[-60:]
		self.temperature_graph.set_data(self.temperature_data_times, self.temperature_data)

		# Reset everything to show the newly plotted data
		self.ax.relim()
		self.ax.autoscale_view()
		plt.draw()
		plt.pause(0.05)
		self.master.after(500, self.Update_Temperature)


	def Run_Measurement( self ):
		try: # running_measurement is implemented as a generator,
			 # so it will just pick up where it left off each time it's called
			is_finished = next(self.running_measurement)
		except OSError:
			print( "Lost Connection With: " + r"\\NICCOMP" )

		if not is_finished:
			self.master.after(1, self.Run_Measurement)

	def Start_Measurement( self ):
		sample_name = self.name_entry.get()
		if( sample_name == "" ):
			messagebox.showerror( "Error", "Must enter a sample name" )
			return
		if( self.temperature_control_toggle.get() ):
			temperatures_to_measure = np.arange( float(self.low_temperature.get()), float(self.high_temperature.get()), float(self.step_temperature.get()) )
		else:
			temperatures_to_measure = [None]
		if( self.bias_control_toggle.get() ):
			biases_to_measure = np.arange( float(self.low_bias.get()), float(self.high_bias.get()), float(self.step_bias.get()) )
		else:
			biases_to_measure = [None]

		self.running_measurement = self.app.Run_Sweep( sample_name, temperatures_to_measure, biases_to_measure )
		self.master.after(1, self.Run_Measurement)

	#def Get_Results();

if( __name__ == "__main__" ):
	root = tk.Tk()
	root.title("FTIR Commander")
	root.configure(background="#333333")
	my_gui = FTIR_GUI(root)
	root.mainloop()
