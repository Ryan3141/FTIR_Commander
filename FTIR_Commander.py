import time
from Temperature_Controller import Temperature_Controller
from Omnic_Controller import Omnic_Controller

#var = input("Enter something: ")
#ser.write(var.encode())

if( __name__ == "__main__" ):
	#temp_controller = Temperature_Controller()

	#old_time = time.time()
	#while True:
	#	new_time = time.time()
	#	temp_controller.Update()
	#	if( new_time - old_time > 0.5 ):
	#		print( temp_controller.GetTemp() )
	#		old_time = new_time


	omnic_controller = Omnic_Controller( directory_for_commands=r"\\NICCOMP\ExportData\Commands", directory_for_results=r"\\NICCOMP\ExportData\Test" )
	#omnic_controller = Omnic_Controller( directory_for_commands=r"\\NICCOMP\ExportData\Commands", directory_for_results=r"C:\Users\Ryan\Documents\Visual Studio 2013\Projects\Auto_Button_Pusher\Auto_Button_Pusher" )

	try:
		omnic_controller.Measure_Background('test')
		omnic_controller.Measure_Sample('test')
		while True:
			time.sleep(5)
	except OSError:
		print( "Lost Connection With: " + r"\\NICCOMP" )
	except:
		omnic_controller.observer.stop()
		print( "Error" )

		omnic_controller.observer.join()

