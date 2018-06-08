WaitFor OMNIC
CtrlText e
#WaitFor Experiment Setup - C:\My Documents\Omnic\Param\Default.exp
# Click on Save As button, must be mouse or else window opens twice for some reason
MouseLClick 634 711
WaitFor Save Experiment As
Text SettingsFile
Tab 2
Enter
MouseLClick 738 558
#WaitFor Experiment Setup - E:\ExportData\Output\SettingsFile.exp
# Click on Ok button
MouseLClick 458 715
Enter
