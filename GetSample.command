WaitFor OMNIC
CtrlText n
Text WindowName
Tab
Enter
WaitFor OMNIC - [WindowName]
CtrlText s
WaitFor Collect Sample
Text Background data
Tab
Enter
WaitFor Confirmation
Enter
WaitFor OMNIC - [WindowName]
AltText f
Down
Down
Enter
WaitFor Save As - Background data
Text Test.csv
Tab 2
Enter
CtrlF4
