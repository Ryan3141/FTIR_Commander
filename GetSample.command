WaitFor OMNIC
CtrlText n
Text WindowName
Tab
Enter
WaitFor OMNIC - [WindowName]
CtrlText s
WaitFor Collect Sample
Text SampleDataName
Tab
Enter
WaitFor Confirmation
Enter
WaitFor OMNIC - [WindowName]
AltText f
Down
Down
Enter
WaitFor Save As - SampleDataName
Text $MeasurementName
Tab 2
Enter
CtrlF4
