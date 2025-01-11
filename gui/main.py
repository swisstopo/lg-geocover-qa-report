import argparse
import os
import sys
from contextlib import suppress
from importlib.metadata import version

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
import pyqtspinner
from loguru import logger
from matplotlib.backends.backend_qt5agg import \
    FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QMovie
from PyQt5.QtWidgets import (QApplication, QDialog, QFileDialog, QLabel,
                             QMainWindow, QMessageBox, QPushButton,
                             QStackedLayout, QTableWidget, QTableWidgetItem,
                             QTabWidget, QVBoxLayout, QWidget)

from geocover_qa.stat import get_lots_perimeter, get_stats_for_issues_gdb
from geocover_qa.utils import get_mapsheets_path, map_network_drive

GPKG_FILEPATH = get_mapsheets_path()


class CustomFileDialog(QFileDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFileMode(QFileDialog.Directory)
        self.setOption(QFileDialog.ShowDirsOnly, True)

    def accept(self):
        selected_dir = self.selectedFiles()[0]
        if selected_dir.endswith("issue.gdb"):
            super().accept()
        else:
            print("Please select a directory that ends with 'issue.gdb'")


class WorkerThread(QThread):
    finished = pyqtSignal(pd.DataFrame, pd.DataFrame)
    error = pyqtSignal(str)  # Signal to emit error messages

    def __init__(self, dir_path, parent=None):
        super().__init__(parent)
        self.dir_path = dir_path

    def run(self):
        try:
            # Call the function and process results
            combined, stats = get_stats_for_issues_gdb(self.dir_path)
            self.finished.emit(combined, stats)
        except Exception as e:
            # Catch exceptions and emit an error signal
            error_message = f"Error while getting stats for {self.dir_path}: {str(e)}"
            self.error.emit(error_message)


class PlotWorkerThread(QThread):
    plot_ready = pyqtSignal()

    def __init__(self, dataframe, canvas, parent=None):
        super().__init__(parent)
        self.dataframe = dataframe
        self.plot_canvas = canvas

    def run(self):
        ch_gdf = gpd.read_file(GPKG_FILEPATH, layer="ch")
        ch_gdf = ch_gdf.set_crs(epsg=2056, allow_override=True)
        lots_perimeter_gdf = get_lots_perimeter(GPKG_FILEPATH)
        # lot_gdf = lots_perimeter[lots_perimeter["Lot"] == lot]

        ax = self.plot_canvas.figure.add_subplot(111)
        ax.clear()
        # ax.plot([0, 1, 2, 3], [0, 1, 4, 9], label="y = x^2")
        # ax.plot(self.data)
        self.dataframe.plot(
            ax=ax, alpha=0.8, facecolor="none", edgecolor="pink", linewidth=1
        )
        ch_gdf.plot(ax=ax, alpha=0.3, facecolor="none", edgecolor="purple", linewidth=3)
        lots_perimeter_gdf.plot(
            ax=ax, alpha=0.8, facecolor="none", edgecolor="pink", linewidth=3
        )

        ax.set_title("Dummy Graph")
        # ax.set_xlim(2.450e6,2.9e6 )
        # ax.set_ylim(1.050e6, 1.35e6)
        ax.legend()
        self.plot_canvas.draw()
        # plt.figure()
        # self.dataframe.plot()
        # plt.savefig("plot.png")  # Save plot as PNG file
        self.plot_ready.emit()


class MainWindow(QMainWindow):
    def __init__(self, start_dir="", gdb_path=None):
        super().__init__()
        self.setWindowTitle("GeoCover QA Analysis")
        self.setGeometry(100, 100, 1200, 800)

        self.setWindowIcon(QIcon("favicon.ico"))

        self.central_widget = QWidget()

        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)

        self.button_select = QPushButton("Select .gdb Directory")
        self.button_select.clicked.connect(lambda: self.load_directory(start_dir))
        self.layout.addWidget(self.button_select)

        self.tabs = QTabWidget()
        self.table_tab = QWidget()
        self.table_layout = QVBoxLayout(self.table_tab)

        self.table = QTableWidget()
        self.table.setSortingEnabled(True)
        self.table_layout.addWidget(self.table)

        self.plot_tab = QWidget()
        self.plot_layout = QVBoxLayout(self.plot_tab)
        # self.plot_widget = QLabel('Plot will appear here')
        self.plot_canvas = FigureCanvas(plt.figure())
        self.plot_layout.addWidget(self.plot_canvas)

        self.tabs.addTab(self.table_tab, "Data Table")
        self.tabs.addTab(self.plot_tab, "Plot")
        self.layout.addWidget(self.tabs)

        self.spinner = pyqtspinner.WaitingSpinner(self)
        self.layout.addWidget(self.spinner)

        self.button_save = QPushButton("Save as Excel")
        self.button_save.clicked.connect(self.save_as_excel)
        self.button_save.setDisabled(True)  # Disabled until data is loaded
        self.layout.addWidget(self.button_save)

        self.button_plot = QPushButton("Plot Data")
        self.button_plot.clicked.connect(self.plot_data)
        self.button_plot.setDisabled(True)  # Disabled until data is loaded
        self.layout.addWidget(self.button_plot)

        self.dataframe = None  # To store the DataFrame
        self.data = None

        # Load directory if provided in command line arguments
        if gdb_path and gdb_path.endswith(".gdb"):
            self.load_directory_from_path(gdb_path)

    def load_directory(self, start_dir=""):
        dialog = CustomFileDialog(self)
        dialog.setDirectory(start_dir)
        if dialog.exec_() == QFileDialog.Accepted:
            dir_path = dialog.selectedFiles()[0]
            self.load_directory_from_path(dir_path)

    def load_directory_from_path(self, dir_path):
        self.spinner.start()
        self.worker = WorkerThread(dir_path)
        self.worker.finished.connect(self.on_data_loaded)
        self.worker.error.connect(self.on_data_error)
        self.worker.start()

    def on_data_loaded(self, combined, df):
        self.dataframe = df  # Store the DataFrame
        self.data = combined
        self.table.setRowCount(df.shape[0])
        self.table.setColumnCount(df.shape[1])
        self.table.setHorizontalHeaderLabels(df.columns)

        for i in range(df.shape[0]):
            for j in range(df.shape[1]):
                self.table.setItem(i, j, QTableWidgetItem(str(df.iat[i, j])))

        # Resize columns to fit contents
        self.table.resizeColumnsToContents()
        self.button_save.setEnabled(True)  # Enable save button
        self.button_plot.setEnabled(True)
        self.spinner.stop()

    def on_data_error(self, error_message):
        # Handle errors (e.g., show a message box)
        self.spinner.stop()
        QMessageBox.critical(self, "Error", error_message)
        print(f"Error: {error_message}")

    def save_as_excel(self):
        if self.dataframe is not None:
            options = QFileDialog.Options()
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save as Excel File",
                "",
                "Excel Files (*.xlsx);;All Files (*)",
                options=options,
            )

            if file_path:
                self.dataframe.to_excel(file_path, index=False)
                print(f"Data saved to {file_path}")

    def plot_data(self):
        if self.data is not None:
            self.spinner.start()
            self.plot_worker = PlotWorkerThread(self.data, self.plot_canvas)
            self.plot_worker.plot_ready.connect(self.on_plot_ready)
            self.plot_worker.start()

    def on_plot_ready(self):
        # pixmap = QPixmap("plot.png")
        # self.plot_widget.setPixmap(pixmap)
        self.tabs.setCurrentIndex(1)  # Switch to plot tab
        self.spinner.stop()


if __name__ == "__main__":
    DEFAULT_DIR = r"\\v0t0020a.adr.admin.ch\topgisprod\10_Production_GC\Administration\QA\Verifications"
    parser = argparse.ArgumentParser(
        description="PyQt5 .gdb directory and DataFrame viewer"
    )
    parser.add_argument("gdb_path", nargs="?", help="Path to the .gdb directory")
    parser.add_argument("--start_dir", help="Initial directory for QFileDialog")
    parser.add_argument(
        "-V", "--version", action="version", version=version("geocover_qa")
    )
    args = parser.parse_args()
    if os.name == "nt":
        map_network_drive(
            "Q",
            r"\\v0t0020a\topgisprod\10_Production_GC\Administration\QA\Verifications",
        )

    if args.gdb_path is None and os.path.isdir(DEFAULT_DIR):
        args.gdb_path = DEFAULT_DIR

        sys.exit()
    app = QApplication(sys.argv)
    main_window = MainWindow(start_dir=args.start_dir, gdb_path=args.gdb_path)
    main_window.show()
    with suppress(ModuleNotFoundError):
        import pyi_splash  # noqa

        pyi_splash.close()
    sys.exit(app.exec())
