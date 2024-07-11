import sys
import platform
import time
import os
import numpy as np
import pandas as pd

import serial

# import socket
# PORT = '/dev/ttyUSB2'
BAUDRATE = 19200
# DATA_PATH = '/mnt/r/crd_G9000/AVXxx/3610-NUV1022/R&D/roofwind/data'
DATA_REFRESH_TIME = 2  # s
PLOT_WINDOW = 5  # min

import serial.tools.list_ports as ls
PORTLIST = [p.device for p in ls.comports()]
print(PORTLIST)

opsystem = platform.system()  # 'Linux', 'Windows', 'Darwin'
print(opsystem)
print(platform.node())  # hostname
## Qt GUI
if 'rasp' in platform.node():  # on a raspberry pi, use PySide6
    from PySide6.QtGui import QPixmap, QIcon, QAction
    from PySide6.QtCore import Qt, QTimer, QSize
    from PySide6.QtWidgets import (
        QApplication,
        QTabWidget,
        QPushButton,
        QMessageBox,
        QTableWidget,
        QTextEdit,
        QLineEdit,
        QToolButton,
        QCheckBox,
        QGridLayout,
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QGroupBox,
        QProgressBar,
        QComboBox,
        QTableWidgetItem,
        QScrollArea,
        QToolBar,
        QMainWindow,
        QFileDialog,
    )
    from PySide6.QtCore import QObject, QThread, Signal

else:
    # use PyQt6
    from PyQt6.QtGui import QPixmap, QIcon, QAction
    from PyQt6.QtCore import Qt, QTimer, QSize
    from PyQt6.QtWidgets import (
        QApplication,
        QTabWidget,
        QPushButton,
        QMessageBox,
        QTableWidget,
        QTextEdit,
        QLineEdit,
        QToolButton,
        QCheckBox,
        QGridLayout,
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QGroupBox,
        QProgressBar,
        QComboBox,
        QTableWidgetItem,
        QScrollArea,
        QToolBar,
        QMainWindow,
        QFileDialog,
    )
    from PyQt6.QtCore import QObject, QThread
    from PyQt6.QtCore import pyqtSignal as Signal

from matplotlib import pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

from windrose import WindroseAxes

import style

global stoprun  # 1 stop thread, 0 keep running


# Step 1: Create a worker class
class Worker(QObject):
    finished = Signal()
    # progress = Signal(int)
    progress = Signal(str)

    def run(self):
        """Long-running task."""
        global stoprun
        stoprun = 0

        with open("par1/port.txt", "r") as f:
            PORT = f.read()

        with open("par1/folder.txt", "r") as f:
            DATA_PATH = f.read()

        wind = serial.Serial(PORT, BAUDRATE)
        print(wind.name)

        start_time = time.time()
        now_time = time.strftime("%Y%m%d_%H%M%S")
        data_path = os.path.join(DATA_PATH, now_time + ".csv")
        self.progress.emit(now_time)
        with open(data_path, "w") as f:
            f.write("epoch_time, clock_time,U_speed_NS,V_speed_WE\n")

        while True:
            if stoprun:
                break

            now = time.time()
            now_time = time.strftime("%Y%m%d_%H%M%S")

            if now - start_time > 3600:  # a new csv every hour
                data_path = os.path.join(DATA_PATH, now_time + ".csv")
                with open(data_path, "w") as f:
                    f.write("epoch_time, clock_time,U_speed_NS,V_speed_WE\n")
                start_time = now
                self.progress.emit(now_time)

            x = wind.readline().decode()
            y = x.split(',')
            u = float(y[1])  # u axis speed, NS
            v = float(y[2])  # v axis speed, WE

            with open(data_path, "a") as f:
                f.write("%s,%s,%s,%s\n" % (now, now_time, u, v))

        self.finished.emit()


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setGeometry(200, 200, 1200, 800)
        self.setWindowTitle("Wind")
        self.set_window_layout()
        self.port = '/dev/ttyUSB2'

    def add_img(self, imgpath, label, x, y):  # image path, label, x scale, y scale
        p1 = QPixmap(imgpath)
        p2 = p1.scaled(
            x,
            y,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        label.setPixmap(p2)

    def set_window_layout(self):
        mainLayout = QVBoxLayout()
        topLayout = QHBoxLayout()
        bottomLayout = QHBoxLayout()
        mainLayout.addLayout(topLayout, 5)
        mainLayout.addLayout(bottomLayout, 95)

        logoLabel = QLabel()
        self.add_img("icons/picarro.png", logoLabel, 250, 100)
        # logoLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        titleLabel = QLabel("Real Time Wind Data Recorder")
        titleLabel.setStyleSheet(style.headline1())
        titleLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        topLayout.addWidget(logoLabel)
        topLayout.addStretch(1)
        topLayout.addWidget(titleLabel)
        topLayout.addStretch(2)

        leftLayout = QVBoxLayout()
        rightLayout = QVBoxLayout()
        gap = QLabel("")
        bottomLayout.addLayout(leftLayout)
        bottomLayout.addWidget(gap)
        bottomLayout.addLayout(rightLayout)

        figure1Layout = QVBoxLayout()
        figure1Layout.setContentsMargins(20, 30, 20, 10)
        box1 = QGroupBox("Time Series Plot")
        box1.setStyleSheet(style.box1())
        box1.setLayout(figure1Layout)

        self.Layout = QVBoxLayout()
        leftLayout.addWidget(box1)
        leftLayout.addLayout(self.Layout)

        figure2Layout = QVBoxLayout()
        figure2Layout.setContentsMargins(20, 30, 20, 10)
        box2 = QGroupBox("Wind Rose Plot")
        box2.setStyleSheet(style.box2())
        box2.setLayout(figure2Layout)
        rightLayout.addWidget(box2)

        # time plot
        self.figure1 = plt.figure()
        self.canvas1 = FigureCanvas(self.figure1)
        self.toolbar1 = NavigationToolbar(self.canvas1, self)
        self.toolbar1.setFixedHeight(30)

        figure1Layout.addWidget(self.canvas1)
        figure1Layout.addWidget(self.toolbar1)

        # windrose plot
        self.figure2 = plt.figure()
        self.canvas2 = FigureCanvas(self.figure2)
        self.toolbar2 = NavigationToolbar(self.canvas2, self)
        self.toolbar2.setFixedHeight(30)

        figure2Layout.addWidget(self.canvas2)
        figure2Layout.addWidget(self.toolbar2)

        self.createLayout1()
        self.createLayout2()

        self.setLayout(mainLayout)

        self.timer_plot = QTimer()
        self.timer_plot.setInterval(DATA_REFRESH_TIME * 1000)
        # self.timer_plot.timeout.connect(lambda: greeter_server.scale_plot(self))
        self.timer_plot.timeout.connect(self.plot_wind)

    def createLayout1(self):
        layout1 = QHBoxLayout()
        layout2 = QHBoxLayout()
        layout3 = QHBoxLayout()
        layout4 = QHBoxLayout()
        self.Layout.addLayout(layout1)
        self.Layout.addLayout(layout2)
        self.Layout.addLayout(layout3)
        self.Layout.addLayout(layout4)

        label11 = QLabel("Wind Velocity (m/s):")
        label12 = QLabel("U-axis (NS):")
        label12.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.uLabel = QLabel()
        self.uLabel.setStyleSheet(style.grey1())

        label13 = QLabel("V-axis (WE):")
        label13.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.vLabel = QLabel()
        self.vLabel.setStyleSheet(style.grey1())

        layout1.addWidget(label11)
        layout1.addWidget(label12)
        layout1.addWidget(self.uLabel)
        layout1.addWidget(label13)
        layout1.addWidget(self.vLabel)

        label21 = QLabel("Store Folder:")
        self.folderLineEdit = QLineEdit("")
        folderButton = QPushButton("Browse")
        folderButton.clicked.connect(self.brouse_folder)
        # folderButton.clicked.connect(lambda: func_tab3.browse_file(self))

        layout2.addWidget(label21)
        layout2.addWidget(self.folderLineEdit)
        layout2.addWidget(folderButton)

        layout5 = QVBoxLayout()
        layout6 = QVBoxLayout()
        layout7 = QVBoxLayout()

        layout4.addLayout(layout7, 70)
        layout4.addLayout(layout5, 15)
        layout4.addLayout(layout6, 15)

        self.StartButton = QToolButton()
        self.StartButton.setIcon(QIcon("icons/start1.png"))
        self.StartButton.setIconSize(QSize(40, 40))
        self.StartButton.clicked.connect(self.start)
        # self.StartButton.clicked.connect(lambda: func_experiment.start_exp(self))
        label1 = QLabel("   Start")
        label1.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout5.addWidget(self.StartButton)
        layout5.addWidget(label1)

        self.StopButton = QToolButton()
        self.StopButton.setIcon(QIcon("icons/stop1.png"))
        self.StopButton.setIconSize(QSize(40, 40))
        self.StopButton.clicked.connect(self.stop)
        self.StopButton.setEnabled(False)
        label2 = QLabel("   Stop")
        label2.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout6.addWidget(self.StopButton)
        layout6.addWidget(label2)

        label41 = QLabel("Data record speed: 4 Hz")
        layout8 = QHBoxLayout()
        # layout9 = QHBoxLayout()
        self.hintLabel = QLabel()
        self.hintLabel.setStyleSheet(style.grey1())

        # layout7.addWidget(label41)
        layout7.addLayout(layout8)
        # layout7.addLayout(layout9)
        layout7.addWidget(self.hintLabel)

        label42 = QLabel("Anemometer port:")
        self.portComboBox = QComboBox()
        self.portComboBox.setFixedWidth(120)
        self.port_get()
        try:
            with open("par1/port.txt", "r") as f:
                temp = f.read()
            self.portComboBox.setCurrentIndex(temp)
        except:
            print("load port failed.")

        portgetButton = QPushButton("Refresh")
        portgetButton.clicked.connect(self.port_get)
        portDetectButton = QPushButton("Detect")
        portDetectButton.clicked.connect(self.port_detect)
        self.portHintLabel = QLabel("  ")

        # layout8.addWidget(label41)
        layout8.addWidget(label42)
        layout8.addWidget(self.portComboBox)
        layout8.addWidget(portgetButton)
        layout8.addWidget(portDetectButton)
        layout8.addWidget(self.portHintLabel)

    def createLayout2(self):
        pass

    # real time display and plot
    def plot_wind(self):


        # time series plot
        try:
            self.figure1.clear()
            ax1 = self.figure1.add_subplot(111)

            data_path = os.path.join(self.folder_path, self.filename + ".csv")
            df = pd.read_csv(data_path)
            wind_u = df["U_speed_NS"]
            wind_v = df["V_speed_WE"]
            time = df["epoch_time"]

            n = PLOT_WINDOW * 60
            if df.shape[0] > n:
                wind_u = wind_u[-n:]
                wind_v = wind_v[-n:]
                time = time[-n:]

            wind_speed = np.sqrt(wind_u ** 2 + wind_v ** 2)
            ax1.quiver(time, wind_speed, wind_u, wind_v)

            # axis label
            ax1.set_xlabel("Clock Time: %s" % time.strftime("%Y-%m-%d"))
            ax1.set_ylabel("Wind Speed, m/s", fontsize=10)

            # add mark
            xx = list(time[::60])
            xmak = []
            for i in xx:
                a = time.strftime('%H:%M', time.localtime(i))
                xmak.append(a)
            ax1.set_xticks(xx)
            ax1.set_xticklabels(xmak, fontsize=8)

            self.canvas1.draw()

            # windrose plot
            self.figure2.clear()

            def wind_uv_to_dir(U, V):
                """
                Calculates the wind direction from the u and v component of wind.
                Takes into account the wind direction coordinates is different than the
                trig unit circle coordinate. If the wind directin is 360 then returns zero
                (by %360)
                Inputs:
                  U = west/east direction (wind from the west is positive, from the east is negative)
                  V = south/noth direction (wind from the south is positive, from the north is negative)
                """
                WDIR = (270 - np.rad2deg(np.arctan2(V, U))) % 360
                return WDIR

            wind_dir = wind_uv_to_dir(wind_u, wind_v)

            rect = [0.1, 0.2, 0.8, 0.7]
            ax = WindroseAxes(self.figure2, rect)
            self.figure2.add_axes(ax)

            ax.bar(wind_dir, wind_speed, normed=True, opening=0.8, edgecolor='white')
            ax.set_legend(title='Wind Speed in m/s', bbox_to_anchor=(-0.1, -0.2))
            self.canvas2.draw()

            # real time values
            self.uLabel.setText(wind_u[-1])
            self.vLabel.setText(wind_v[-1])

            self.hintLabel.setText(self.startText + "Real time display...")

        except:
            self.hintLabel.setText(self.startText + "Failed to real time display.")

    def reportProgress(self, n):
        self.filename = n

    def runLongTask(self):
        PORT = self.portComboBox.currentText()

        # Step 2: Create a QThread object
        self.thread = QThread()
        # Step 3: Create a worker object
        self.worker = Worker()
        # Step 4: Move worker to the thread
        self.worker.moveToThread(self.thread)
        # Step 5: Connect signals and slots
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.progress.connect(self.reportProgress)
        # Step 6: Start the thread
        self.thread.start()


    def start(self):
        # error check
        tag = self.port_detect()
        if not tag:
            self.hintLabel.setText(" ! Anemometer is not connected.")

        if tag:
            self.folder_path = self.folderLineEdit.text()
            if not os.path.isdir(self.folder_path):
                self.hintLabel.setText("! Folder to store data does not exist.")
                tag = 0

        if tag:
            try:
                self.runLongTask()
                self.timer_plot.start()

                self.StartButton.setEnabled(False)
                self.StopButton.setEnabled(True)
                # print('Record started.')
                self.startText = "Recording started at: %s. " % time.strftime("%Y-%m-%d %H:%M:%S")
                self.hintLabel.setText(self.startText)
            except:
                self.hintLabel.setText(" ! Error start.")



    def stop(self):
        global stoprun
        stoprun = 1

        self.timer_plot.stop()
        self.StartButton.setEnabled(True)
        self.StopButton.setEnabled(False)
        # print('Record stopped.')
        self.hintLabel.setText("Recording stopped at: %s. " % time.strftime("%Y-%m-%d %H:%M:%S"))


    def brouse_folder(self):
        folder = QFileDialog.getExistingDirectory()
        self.folderLineEdit.setText(folder)

    def port_get(self):
        PORTLIST = [p.device for p in ls.comports()]
        self.portComboBox.clear()
        self.portComboBox.addItems(PORTLIST)

    def port_detect(self):
        port = self.portComboBox.currentText()
        wind = serial.Serial(port, BAUDRATE, timeout = 5)
        x = wind.readline().decode()
        if x:
            with open("port.txt", "w") as f:
                f.write(port)
            self.hintLabel.setText("\u2713")
            print("Anemometer connected.")
            # print(x)
            return 1
        else:
            self.hintLabel.setText("\u2713")
            print("Anemometer NOT connected.")
            return 0


def main():
    app = QApplication(sys.argv)
    window = Window()
    app.setWindowIcon(QIcon("icons/p2.jpeg"))
    window.show()
    app.exec()


if __name__ == "__main__":
    main()

# @author: Yilin Shi | 2024.4.25
# shiyilin890@gmail.com
# Bog the Fat Crocodile vvvvvvv
#                       ^^^^^^^
