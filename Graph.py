# -*- coding: utf-8 -*-
#
# Licensed under the terms of the MIT License
# Copyright (c) 2015 Pierre Raybaut

"""
Simple example illustrating Qt Charts capabilities to plot curves with 
a high number of points, using OpenGL accelerated series
"""

from FTIR_Commander.Install_If_Necessary import Ask_For_Install
try:
	from PyQt5.QtChart import QChart, QChartView, QLineSeries, QDateTimeAxis, QValueAxis
except:
	Ask_For_Install( "PyQtChart" )
	from PyQt5.QtChart import QChart, QChartView, QLineSeries, QDateTimeAxis, QValueAxis

from PyQt5.QtGui import QPolygonF, QPainter, QBrush, QGradient, QLinearGradient, QColor, QFont, QPen
from PyQt5.QtCore import Qt, QDateTime, QDate, QTime, QPointF
from PyQt5.QtWidgets import QMainWindow

import numpy as np


class Graph(QChartView):
	def __init__(self, parent=None):
		super().__init__(parent=parent)
		self.setpoint_temperature = None

		self.chart = QChart()
		self.chart.layout().setContentsMargins(0, 0, 0, 0)
		self.chart.legend().hide()
		#self.chart.legend().setAlignment( Qt.AlignRight )

		self.setChart( self.chart )
		self.setRenderHint(QPainter.Antialiasing)
		self.chart.setPlotAreaBackgroundBrush( QBrush(Qt.black) )
		self.chart.setPlotAreaBackgroundVisible( True )

		self.setpointTemperatureSeries = QLineSeries( self.chart )
		pen = self.setpointTemperatureSeries.pen()
		pen.setWidthF(2.)
		pen.setColor( Qt.green )
		self.setpointTemperatureSeries.setPen( pen )
		#self.setpointTemperatureSeries.setUseOpenGL( True )
		self.chart.addSeries( self.setpointTemperatureSeries )

		self.temperatureSeries = QLineSeries( self.chart )
		pen = self.temperatureSeries.pen()
		pen.setWidthF(2.)
		pen.setColor( Qt.red )
		self.temperatureSeries.setPen( pen )
		self.chart.addSeries( self.temperatureSeries )

		self.pidOutputSeries = QLineSeries( self.chart )
		pen = self.pidOutputSeries.pen()
		pen.setWidthF(2.)
		pen.setColor( Qt.blue )
		self.pidOutputSeries.setPen( pen )
		self.chart.addSeries( self.pidOutputSeries )

		# The following 2 series are just for labeling the latest temperature
		self.current_temp_label_series = QLineSeries();
		self.current_temp_label_series.setPointLabelsVisible(True);
		self.current_temp_label_series.setPointLabelsClipping(False);
		self.current_temp_label_series.setPointLabelsColor(Qt.red);
		self.current_temp_label_series.setPointLabelsFormat("Current Temp: @yPoint K");
		self.chart.addSeries( self.current_temp_label_series )

		self.set_temp_label_series = QLineSeries();
		self.set_temp_label_series.setPointLabelsVisible(True);
		self.set_temp_label_series.setPointLabelsClipping(False);
		self.set_temp_label_series.setPointLabelsColor(Qt.green);
		self.set_temp_label_series.setPointLabelsFormat("Set Temp: @yPoint K");
		self.chart.addSeries( self.set_temp_label_series )

		self.debug_series = QLineSeries();
		self.debug_series.setPointLabelsVisible(True);
		self.debug_series.setPointLabelsClipping(False);
		self.debug_series.setPointLabelsColor(Qt.red);
		#self.debug_series.setPointLabelsFormat("Current Temp: @yPoint K");
		self.chart.addSeries( self.debug_series )

		self.number_of_samples_to_keep = 2 * 5 * 60

		self.xMin = QDateTime.currentDateTime().toMSecsSinceEpoch()
		self.xMax = QDateTime.currentDateTime().toMSecsSinceEpoch()
		self.yMin = 400
		self.yMax = 0

		#self.chart.createDefaultAxes()
		#x_axis = QValueAxis()
		x_axis = QDateTimeAxis()
		x_axis.setTitleText( "Time" )
		x_axis.setFormat("HH:mm:ss")
		self.chart.addAxis( x_axis, Qt.AlignBottom )
		self.temperatureSeries.attachAxis( x_axis )
		self.pidOutputSeries.attachAxis( x_axis )
		self.setpointTemperatureSeries.attachAxis( x_axis )
		self.current_temp_label_series.attachAxis( x_axis )
		self.set_temp_label_series.attachAxis( x_axis )
		startDate = QDateTime.currentDateTime().addSecs( -5 * 60 )
		endDate = QDateTime.currentDateTime().addSecs( 5 * 60 )
		#startDate = QDateTime(QDate(2017, 1, 9), QTime(17, 25, 0))
		#endDate = QDateTime(QDate(2017, 1, 9), QTime(17, 50, 0))
		#self.chart.axisX().setRange( startDate, endDate )
		#self.chart.axisX().setRange( 0, 100 )

		y_axis = QValueAxis()
		y_axis.setTitleText( "Temperature (K)" )
		self.chart.addAxis( y_axis, Qt.AlignLeft )
		self.temperatureSeries.attachAxis( y_axis )
		self.setpointTemperatureSeries.attachAxis( y_axis )
		self.current_temp_label_series.attachAxis( y_axis )
		self.set_temp_label_series.attachAxis( y_axis )
		self.chart.axisY().setRange( 0, 400 )
		#self.chart.axisY().setRange( 260., 290. )

		y_axis2 = QValueAxis()
		y_axis2.setTitleText( "Heater Power (%)" )
		self.chart.addAxis( y_axis2, Qt.AlignRight )
		self.pidOutputSeries.attachAxis( y_axis2 )
		y_axis2.setRange( 0, 100 )

		self.temperatureSeries.pointAdded.connect( self.Rescale_Axes )
		self.pidOutputSeries.pointAdded.connect( self.Rescale_Axes2 )
		#self.setpointTemperatureSeries.pointAdded.connect( self.Rescale_Axes )

		self.setRubberBand( QChartView.HorizontalRubberBand )

		# Customize chart title
		font = QFont()
		font.setPixelSize(24);
		self.chart.setTitleFont(font);
		self.chart.setTitleBrush(QBrush(Qt.white));

		## Customize chart background
		#backgroundGradient = QLinearGradient()
		#backgroundGradient.setStart(QPointF(0, 0));
		#backgroundGradient.setFinalStop(QPointF(0, 1));
		#backgroundGradient.setColorAt(0.0, QColor(0x000147));
		#backgroundGradient.setColorAt(1.0, QColor(0x000117));
		#backgroundGradient.setCoordinateMode(QGradient.ObjectBoundingMode);
		#self.chart.setBackgroundBrush(backgroundGradient);
		transparent_background = QBrush(QColor(0,0,0,0))
		self.chart.setBackgroundBrush( transparent_background )

		# Customize axis label font
		labelsFont = QFont()
		labelsFont.setPixelSize(16);
		x_axis.setLabelsFont(labelsFont)
		y_axis.setLabelsFont(labelsFont)
		y_axis2.setLabelsFont(labelsFont)
		x_axis.setTitleFont(labelsFont)
		y_axis.setTitleFont(labelsFont)
		y_axis2.setTitleFont(labelsFont)

		# Customize axis colors
		axisPen = QPen(QColor(0xd18952))
		axisPen.setWidth(2)
		x_axis.setLinePen(axisPen)
		y_axis.setLinePen(axisPen)
		y_axis2.setLinePen(axisPen)

		# Customize axis label colors
		axisBrush = QBrush(Qt.white)
		x_axis.setLabelsBrush(axisBrush)
		y_axis.setLabelsBrush(axisBrush)
		y_axis2.setLabelsBrush(axisBrush)
		x_axis.setTitleBrush(axisBrush)
		y_axis.setTitleBrush(axisBrush)
		y_axis2.setTitleBrush(axisBrush)

		## add the text label at the top:
		#textLabel = QCPItemText(customPlot);
		##textLabel.setPositionAlignment( Qt.AlignTop|Qt.AlignHCenter );
		#textLabel.position.setType(QCPItemPosition.ptAxisRectRatio);
		#textLabel.position.setCoords(0.5, 0); # place position at center/top of axis rect
		#textLabel.setText("Text Item Demo");
		#textLabel.setFont(QFont(font().family(), 16)); # make font a bit larger
		#textLabel.setPen(QPen(Qt.black)); # show black border around text

		## add the arrow:
		#self.arrow = QCPItemLine(customPlot);
		#self.arrow.start.setParentAnchor(textLabel.bottom);
		#self.arrow.end.setCoords(4, 1.6); # point to (4, 1.6) in x-y-plot coordinates
		#self.arrow.setHead(QCPLineEnding.esSpikeArrow);

	def set_title(self, title):
		self.chart.setTitle(title)

	def add_new_pid_output_data_point( self, x, y ):
		x_as_millisecs = x.toMSecsSinceEpoch()
		self.pidOutputSeries.append( x_as_millisecs, y )
		self.repaint()

	def add_new_data_point( self, x, y ):
		x_as_millisecs = x.toMSecsSinceEpoch()
		self.temperatureSeries.append( x_as_millisecs, y )
		self.current_temp_label_series.clear()
		self.current_temp_label_series.append( x_as_millisecs, y )
		if( self.setpoint_temperature ):
			self.setpointTemperatureSeries.append( x_as_millisecs, self.setpoint_temperature )
			self.set_temp_label_series.clear()
			self.set_temp_label_series.append( x_as_millisecs, self.setpoint_temperature )
		else:
			self.set_temp_label_series.clear()

		num_of_datapoints = self.temperatureSeries.count()
		#if( num_of_datapoints > self.number_of_samples_to_keep ):
		#	self.number_of_samples_to_keep.
		#print( x_as_millisecs, y )
		#self.chart.scroll( x_as_millisecs - 5 * 60 * 1000, x_as_millisecs )
		#self.temperatureSeries.append( x, float(y) )
		self.repaint()

	def Rescale_Axes2( self, index ):
		x = self.pidOutputSeries.at( index ).x()
		x_rescaled = False
		if( x < self.xMin ):
			self.xMin = x
			x_rescaled = True
		if( x > self.xMax ):
			self.xMax = x
			x_rescaled = True
		if( x_rescaled ):
			full_range = min( self.xMax - self.xMin, 5 * 60 * 1000 )
			margin = full_range * 0.05

			self.chart.axisX().setRange( QDateTime.fromMSecsSinceEpoch(self.xMax - full_range - margin), QDateTime.fromMSecsSinceEpoch(self.xMax + margin) )
			
	def Rescale_Axes( self, index ):
		x = self.temperatureSeries.at( index ).x()
		x_rescaled = False
		if( x < self.xMin ):
			self.xMin = x
			x_rescaled = True
		if( x > self.xMax ):
			self.xMax = x
			x_rescaled = True
		if( x_rescaled ):
			full_range = min( self.xMax - self.xMin, 5 * 60 * 1000 )
			margin = full_range * 0.05

			self.chart.axisX().setRange( QDateTime.fromMSecsSinceEpoch(self.xMax - full_range - margin), QDateTime.fromMSecsSinceEpoch(self.xMax + margin) )
			
		y = self.temperatureSeries.at( index ).y()
		y_rescaled = False
		if( y < self.yMin ):
			self.yMin = y
			y_rescaled = True
		if( y > self.yMax ):
			self.yMax = y
			y_rescaled = True
		if( y_rescaled ):
			full_range = self.yMax - self.yMin
			margin = full_range * 0.05
			self.chart.axisY().setRange( self.yMin - margin, self.yMax + margin )
			
