import psutil
import time
import sys
from PyQt6 import QtWidgets, QtCore, QtGui

# Global variable to store the initial network stats when the application launches.
initial_network_stats = {}
# Global variable to hold the single instance of the NetworkUsageWindow.
# Using a list allows us to reassign None to it easily from within a method.
_current_usage_window_instance = [None] 

# NetworkSpeedMonitor class to handle real-time speed data collection
class NetworkSpeedMonitor(QtCore.QObject):
    speed_updated = QtCore.pyqtSignal(str) 

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_net_io_counters = psutil.net_io_counters()
        self._last_time = time.monotonic()
        
        global initial_network_stats
        initial_network_stats = psutil.net_io_counters(pernic=True)

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(1000) # Update every 1000 ms (1 second)
        self._timer.timeout.connect(self._update_speed)
        self._timer.start()

    def _update_speed(self):
        current_net_io_counters = psutil.net_io_counters()
        current_time = time.monotonic()

        time_diff = current_time - self._last_time
        
        if time_diff <= 0: 
            self.speed_updated.emit("Calculating...") 
            return

        download_bytes_diff = current_net_io_counters.bytes_recv - self._last_net_io_counters.bytes_recv
        upload_bytes_diff = current_net_io_counters.bytes_sent - self._last_net_io_counters.bytes_sent

        download_speed_kbps = (download_bytes_diff / time_diff) / 1024
        upload_speed_kbps = (upload_bytes_diff / time_diff) / 1024

        self._last_net_io_counters = current_net_io_counters
        self._last_time = current_time

        speed_str = f"↓ {download_speed_kbps:.1f} KB/s   ↑ {upload_speed_kbps:.1f} KB/s"
        self.speed_updated.emit(speed_str)

# SpeedHUD class for the PyQt6 GUI (main indicator)
class SpeedHUD(QtWidgets.QWidget):
    clicked = QtCore.pyqtSignal() # Custom signal to emit when the HUD is clicked

    def __init__(self):
        super().__init__()
        self.init_ui()
        
        self.monitor = NetworkSpeedMonitor(self)
        self.monitor.speed_updated.connect(self.label.setText)

    def init_ui(self):
        self.setWindowTitle("Speed HUD")
        
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint |       # No window border or title bar
            QtCore.Qt.WindowType.WindowStaysOnTopHint |      # Keep window on top of others
            QtCore.Qt.WindowType.Tool                        # Prevents window from appearing in taskbar/Alt+Tab
        )

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background:rgba(0,0,0,150);") # Slightly opaque background for the HUD itself for visibility

        # Create a layout for the contents of the HUD
        hud_content_layout = QtWidgets.QHBoxLayout(self)
        hud_content_layout.setContentsMargins(0, 0, 0, 0)
        hud_content_layout.setSpacing(0) # No spacing between label and button

        # Text display label
        self.label = QtWidgets.QLabel("Calculating...", self)
        self.label.setFont(QtGui.QFont("Segoe UI", 11, QtGui.QFont.Weight.Bold))
        self.label.setStyleSheet("color: lime; background-color: rgba(0, 0, 0, 180); border-radius: 5px; padding: 3px; padding-left: 5px; padding-right: 5px;") 
        self.label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        hud_content_layout.addWidget(self.label, 1) # Label takes most space

        # Minimize button
        self.minimize_button = QtWidgets.QPushButton("—", self) # Unicode EM DASH
        self.minimize_button.setFixedSize(25, 30) # Fixed size for the button
        self.minimize_button.setFont(QtGui.QFont("Segoe UI", 12, QtGui.QFont.Weight.Bold))
        self.minimize_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 150);
                color: #CCC;
                border: none;
                border-radius: 5px; /* Match overall border-radius */
            }
            QPushButton:hover {
                background-color: #333;
                color: #FFF;
            }
            QPushButton:pressed {
                background-color: #555;
            }
        """)
        # Connect minimize button to minimize the HUD itself
        self.minimize_button.clicked.connect(self.showMinimized) 
        hud_content_layout.addWidget(self.minimize_button)

        self.setLayout(hud_content_layout) # Set the main layout for the window

        self.set_initial_position()

    def set_initial_position(self):
        screen = QtWidgets.QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.geometry() 
            
            window_width = 250 + 25 # Label width + button width
            window_height = 30 
            
            # Position it at the very bottom-left of the screen, near the Start button
            # 'x' offset for a slight margin from the left edge.
            # 'y' position is the total screen height minus the window height,
            # placing it directly on the bottom edge (which is usually the taskbar)
            x = screen_geometry.left() + 15 # A bit more offset from the absolute left edge
            y = screen_geometry.bottom() - window_height - 5 # 5px above bottom edge to ensure it's on taskbar

            self.setGeometry(x, y, window_width, window_height)

    # Mouse event handlers for dragging and clicking the main HUD window
    def mousePressEvent(self, event: QtGui.QMouseEvent):
        # We only want to enable dragging if the click is on the label itself,
        # not the minimize button.
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            # Check if the click occurred within the label's geometry
            if self.label.geometry().contains(event.position().toPoint()):
                self.old_pos = event.globalPosition().toPoint()
                self._is_dragging = True
            else:
                self._is_dragging = False
            # Emit clicked signal regardless of whether dragging started
            self.clicked.emit() 
        elif event.button() == QtCore.Qt.MouseButton.RightButton:
            pass 

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        if event.buttons() == QtCore.Qt.MouseButton.LeftButton and self._is_dragging and hasattr(self, 'old_pos'):
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._is_dragging = False
            if hasattr(self, 'old_pos'):
                del self.old_pos


# New window to show detailed network usage information
class NetworkUsageWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # WA_DeleteOnClose ensures the object is destroyed when the window is closed
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose) 
        self.old_pos = None # Initialize for dragging
        self._is_dragging = False # Flag to control dragging in mouseMoveEvent
        self.init_ui()
        self.update_usage_display() # Populate initial data

    def init_ui(self):
        self.setWindowTitle("Network Usage Details")
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint |
            QtCore.Qt.WindowType.WindowStaysOnTopHint |
            QtCore.Qt.WindowType.Tool 
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(20, 20, 20, 240); 
                border: 1px solid #444; 
                border-radius: 12px;
            }
            QLabel {
                color: #E0E0E0; /* Light gray for general text */
            }
        """)
        
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20) # More padding for a "classy" look

        # Custom Title Bar for dragging (since frameless)
        self.title_bar_widget = QtWidgets.QWidget(self)
        self.title_bar_widget.setFixedHeight(40) # Set a fixed height for the draggable area
        self.title_bar_widget.setStyleSheet("background-color: transparent;") 
        self.title_bar_layout = QtWidgets.QHBoxLayout(self.title_bar_widget)
        self.title_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.title_bar_layout.setSpacing(0)

        title_label = QtWidgets.QLabel("Network Usage Details", self)
        title_label.setFont(QtGui.QFont("Segoe UI", 14, QtGui.QFont.Weight.Bold))
        title_label.setStyleSheet("color: #4CAF50;") # Green title
        title_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter) # Center title in title bar

        # Close button for the detailed window
        close_btn = QtWidgets.QPushButton("✕", self) # Unicode 'X' character
        close_btn.setFixedSize(24, 24)
        close_btn.setFont(QtGui.QFont("Segoe UI", 12, QtGui.QFont.Weight.DemiBold)) # Corrected Weight.DemiBold
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #999;
                border: none;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #555;
                color: #FFF;
            }
            QPushButton:pressed {
                background-color: #777;
            }
        """)
        close_btn.clicked.connect(self.close) # Close this specific window

        self.title_bar_layout.addWidget(title_label, 1) # Title takes available space
        self.title_bar_layout.addWidget(close_btn)
        main_layout.addWidget(self.title_bar_widget)
        main_layout.addSpacing(15) # Space after title bar

        # Scroll area for interface details
        self.scroll_area = QtWidgets.QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("border: none; background-color: transparent;") 

        self.scroll_content = QtWidgets.QWidget()
        self.scroll_layout = QtWidgets.QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_content.setStyleSheet("background:transparent;")
        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area)

        # Bottom section for notes and general info (if needed)
        self.note_label = QtWidgets.QLabel(
            "<span style='color: #888; font-size: 9pt; font-style: italic;'>"
            "Note: 'Overall Totals' reflect data since your last system boot.<br>"
            "'Usage Since App Launch' is data transferred while this app has been running.<br>"
            "Full daily/monthly tracking would require continuous data logging and persistence.</span>",
            self
        )
        self.note_label.setWordWrap(True)
        self.note_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.note_label)

        self.setLayout(main_layout)
        
        self.resize(450, 550) # Increased default size for better layout
        self.center_on_screen()

    def center_on_screen(self):
        screen = QtWidgets.QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.geometry()
            x = (screen_geometry.width() - self.width()) // 2
            y = (screen_geometry.height() - self.height()) // 2
            self.move(x, y)

    def update_usage_display(self):
        # Clear previous content in the scroll area before adding new data
        for i in reversed(range(self.scroll_layout.count())): 
            widget = self.scroll_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        current_stats = psutil.net_io_counters(pernic=True)
        
        # --- Overall Totals Since Last Boot ---
        overall_group = QtWidgets.QGroupBox("Overall Totals Since System Boot", self)
        overall_group.setFont(QtGui.QFont("Segoe UI", 11, QtGui.QFont.Weight.Bold))
        overall_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #555;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                color: #FFF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center; 
                padding: 0 10px;
                background-color: rgba(20, 20, 20, 240); 
            }
        """)
        overall_layout = QtWidgets.QFormLayout(overall_group)
        overall_layout.setContentsMargins(15, 15, 15, 15)
        
        total_recv_boot = 0
        total_sent_boot = 0
        for nic, stats in current_stats.items():
            total_recv_boot += stats.bytes_recv
            total_sent_boot += stats.bytes_sent
        
        overall_layout.addRow(
            QtWidgets.QLabel("<span style='color: #AAA;'>Received:</span>"), 
            QtWidgets.QLabel(f"<span style='color: lime; font-weight: bold;'>{self._bytes_to_human(total_recv_boot)}</span>")
        )
        overall_layout.addRow(
            QtWidgets.QLabel("<span style='color: #AAA;'>Sent:</span>"), 
            QtWidgets.QLabel(f"<span style='color: lime; font-weight: bold;'>{self._bytes_to_human(total_sent_boot)}</span>")
        )
        self.scroll_layout.addWidget(overall_group)
        self.scroll_layout.addSpacing(15)

        # --- Usage Since Application Launch (Per Interface) ---
        session_group = QtWidgets.QGroupBox("Usage Since Application Launch", self)
        session_group.setFont(QtGui.QFont("Segoe UI", 11, QtGui.QFont.Weight.Bold))
        session_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #555;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                color: #FFF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center; 
                padding: 0 10px;
                background-color: rgba(20, 20, 20, 240); 
            }
        """)
        session_layout = QtWidgets.QVBoxLayout(session_group)
        session_layout.setContentsMargins(15, 15, 15, 15)

        total_session_recv = 0
        total_session_sent = 0

        for nic, current_nic_stats in current_stats.items():
            initial_nic_stats = initial_network_stats.get(nic)

            session_recv = 0
            session_sent = 0
            status_text = ""
            
            if initial_nic_stats:
                session_recv = current_nic_stats.bytes_recv - initial_nic_stats.bytes_recv
                session_sent = current_nic_stats.bytes_sent - initial_nic_stats.bytes_sent
                
                if session_recv < 0 or session_sent < 0:
                    session_recv = current_nic_stats.bytes_recv 
                    session_sent = current_nic_stats.bytes_sent
                    status_text = " <span style='color: #FFC107; font-size: 8pt;'>(Counter reset detected)</span>" 
                
            else:
                session_recv = current_nic_stats.bytes_recv
                session_sent = current_nic_stats.bytes_sent
                status_text = " <span style='color: #FFC107; font-size: 8pt;'>(New interface since launch)</span>"


            total_session_recv += session_recv
            total_session_sent += session_sent

            # Use QHBoxLayout for each NIC to align name and data
            nic_h_layout = QtWidgets.QHBoxLayout()
            nic_name_label = QtWidgets.QLabel(f"<span style='color: #90CAF9;'>{nic}:</span>") 
            nic_name_label.setFont(QtGui.QFont("Segoe UI", 10))
            
            nic_data_label = QtWidgets.QLabel(
                f"<span style='color: lime;'>↓ {self._bytes_to_human(session_recv)}   ↑ {self._bytes_to_human(session_sent)}</span>{status_text}"
            )
            nic_data_label.setFont(QtGui.QFont("Segoe UI", 10, QtGui.QFont.Weight.DemiBold))
            nic_data_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

            nic_h_layout.addWidget(nic_name_label)
            nic_h_layout.addStretch(1) 
            nic_h_layout.addWidget(nic_data_label)
            session_layout.addLayout(nic_h_layout)

        # Add total session usage at the end of this group
        total_session_h_layout = QtWidgets.QHBoxLayout()
        total_session_label = QtWidgets.QLabel("<span style='color: #FFF; font-weight: bold;'>Total Session Usage:</span>")
        total_session_label.setFont(QtGui.QFont("Segoe UI", 11))
        
        total_session_data_label = QtWidgets.QLabel(
            f"<span style='color: lime; font-weight: bold;'>↓ {self._bytes_to_human(total_session_recv)}   ↑ {self._bytes_to_human(total_session_sent)}</span>"
        )
        total_session_data_label.setFont(QtGui.QFont("Segoe UI", 11, QtGui.QFont.Weight.Bold))
        total_session_data_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        total_session_h_layout.addWidget(total_session_label)
        total_session_h_layout.addStretch(1)
        total_session_h_layout.addWidget(total_session_data_label)
        session_layout.addLayout(total_session_h_layout)

        self.scroll_layout.addWidget(session_group)
        self.scroll_layout.addStretch(1) 

    def _bytes_to_human(self, nbytes):
        """Convert bytes to a human-readable format (B, KB, MB, GB, TB)."""
        if nbytes < 0: return "0 B" 
        
        symbols = ('B', 'KB', 'MB', 'GB', 'TB', 'PB') 
        prefix = {}
        for i, s in enumerate(symbols):
            prefix[s] = 1 << (i * 10)
        
        for s in reversed(symbols):
            if nbytes >= prefix[s]:
                return f"{nbytes / prefix[s]:.2f} {s}"
        return f"{nbytes:.2f} B"

    # Mouse event handlers for dragging the frameless info window
    def mousePressEvent(self, event: QtGui.QMouseEvent):
        # Only start dragging if the left button is pressed and the click is within the title bar widget
        if event.button() == QtCore.Qt.MouseButton.LeftButton and \
           self.title_bar_widget.geometry().contains(event.position().toPoint()):
            self.old_pos = event.globalPosition().toPoint()
            self._is_dragging = True
            event.accept()
        else:
            self._is_dragging = False

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        if event.buttons() == QtCore.Qt.MouseButton.LeftButton and self._is_dragging and hasattr(self, 'old_pos'):
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()
            event.accept()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._is_dragging = False
            if hasattr(self, 'old_pos'):
                del self.old_pos
            event.accept()

    # Override closeEvent to clear the global reference when the window is closed
    def closeEvent(self, event: QtGui.QCloseEvent):
        global _current_usage_window_instance
        if _current_usage_window_instance[0] is self: # Ensure we're clearing *this* instance
            _current_usage_window_instance[0] = None
        super().closeEvent(event)


# Main execution block
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    
    hud = SpeedHUD()
    hud.show()

    def show_usage_window():
        global _current_usage_window_instance
        
        # Check if an instance exists and is a valid (not deleted) QObject
        if _current_usage_window_instance[0] is not None and \
           QtCore.QCoreApplication.instance().topLevelWidgets().__contains__(_current_usage_window_instance[0]):
            
            # If it's minimized, restore it
            if _current_usage_window_instance[0].isMinimized():
                _current_usage_window_instance[0].showNormal()
            
            # Bring it to front and activate
            _current_usage_window_instance[0].update_usage_display() # Refresh data
            _current_usage_window_instance[0].raise_()
            _current_usage_window_instance[0].activateWindow()
        else:
            # If no instance exists or the old one was deleted, create a new one
            _current_usage_window_instance[0] = NetworkUsageWindow()
            _current_usage_window_instance[0].show()

    hud.clicked.connect(show_usage_window)

    sys.exit(app.exec())