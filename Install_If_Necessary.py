

from tkinter import messagebox, Tk
import subprocess
import sys

def install(package):
    subprocess.call([sys.executable, "-m", "pip", "install", package])

def Ask_For_Install( package_name ):
	root = Tk()
	root.withdraw()
	root.lift()
	root.attributes("-topmost", True)
	should_install_missing_library = messagebox.askyesno( "Install Missing Library?", "run: pip install " + package_name + "?" )
	if should_install_missing_library:
		install( package_name )
	else:
		raise ImportError( "Error importing " + package_name )

