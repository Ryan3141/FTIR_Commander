WaitFor OMNIC
CtrlText e
WaitFor Experiment Setup - C:\My Documents\Omnic\Param\Default.exp
Tab
Text $Number_Of_Scans #32
Tab
Text $Resolution #16 - 1,2,4,8,16,32
Tab 21
Right
Tab
Text $Gain # 4 - 1, 2, 4, 8, Autogain
Tab
Text $Velocity #0.6329 - 0.0158, 0.0317, 0.0475, 0.0633, 0.1581, 0.3165, 0.4747, 0.6329, 0.9494, 1.2659, 1.8988, 2.5317, 3.1647, 3.7974, 4.4303, 4.7468, 5.0632, 5.6961, 6.3290, 6.9619, 7.5948, 8.2277
Tab
Text $Aperture #50
Tab 2
Text $Sample_Compartment # Main - Main, Right AEM, Left AEM
Tab
Text $Detector # DTGS TEC - DTGS TEC, InSb
Tab 2
Text $Source # IR - Off, External, IR, White light
Tab 4
Text $Spectral_Range_High # 5000
Tab
Text $Spectral_Range_Low # 2100
Tab 3
Enter
WaitFor OMNIC

# 13 Tabs to spectral range high
