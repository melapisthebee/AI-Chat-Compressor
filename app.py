import sys
from PyQt6.QtWidgets import QApplication
from gui.main_window import MainWindow

def main():
    """
    Main application entry point. Initializes the global QApplication environment
    and shifts orchestration to the reactive GUI layout loop.
    """
    # 1. Initialize the global platform window application instance
    app = QApplication(sys.argv)
    
    # 2. Instantiates your non-blocking main workspace window
    window = MainWindow()
    window.show()
    
    # 3. Safe handoff execution to the underlying Qt thread runtime loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()