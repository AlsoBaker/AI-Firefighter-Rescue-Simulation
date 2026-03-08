# visualize.py

import sys
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QSlider, QGridLayout)
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QColor, QPainter, QFont, QBrush, QPen
from PyQt5.QtWidgets import QFrame

from fire import spread_fire
from firefighter import move_firefighter, initialize_firefighters, get_firefighter_stats
from metrics import SimulationMetrics
from config import *


class GridCanvas(QFrame):
    """Canvas for rendering the grid"""
    
    def __init__(self, grid):
        super().__init__()
        self.grid = grid
        self.cell_size = 30
        self.animation_frame = 0
        
        # Colors
        self.colors = {
            EMPTY: QColor(50, 50, 50),
            PERSON: QColor(100, 200, 100),
            PERSON_DANGER: QColor(255, 150, 0),
            SHELTER: QColor(100, 200, 255),
            FIRE: QColor(255, 50, 50),
            OBSTACLE: QColor(0, 0, 0),
            FIREFIGHTER: QColor(255, 150, 50),
        }
        
        self.fire_colors = [
            QColor(255, 50, 50),
            QColor(255, 100, 0),
            QColor(255, 150, 0)
        ]
        
        self.setStyleSheet("background-color: #1a1a1a; border: 2px solid #333333;")
    
    def sizeHint(self):
        return QSize(COLS * self.cell_size + 20, ROWS * self.cell_size + 20)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw grid
        offset_x = 10
        offset_y = 10
        
        for r in range(ROWS):
            for c in range(COLS):
                x = offset_x + c * self.cell_size
                y = offset_y + r * self.cell_size
                
                cell_type = self.grid[r, c]
                
                # Get color
                if cell_type == FIRE:
                    # Animate fire
                    color = self.fire_colors[self.animation_frame % len(self.fire_colors)]
                else:
                    color = self.colors.get(cell_type, QColor(50, 50, 50))
                
                # Draw cell
                painter.fillRect(x, y, self.cell_size, self.cell_size, QBrush(color))
                painter.drawRect(x, y, self.cell_size, self.cell_size)
                
                # Draw emoji icons
                font = QFont()
                font.setPointSize(12)
                painter.setFont(font)
                
                emoji = ""
                if cell_type == FIREFIGHTER:
                    emoji = "🧑‍🚒"
                elif cell_type == PERSON:
                    emoji = "🚶"
                elif cell_type == PERSON_DANGER:
                    emoji = "😱"
                elif cell_type == SHELTER:
                    emoji = "🛡️"
                
                if emoji:
                    painter.drawText(x, y, self.cell_size, self.cell_size, 
                                   Qt.AlignCenter, emoji)
        
        painter.end()
    
    def update_grid(self, grid):
        self.grid = grid
        self.animation_frame += 1
        self.update()


class PyQt5Simulation(QMainWindow):
    """Main simulation window"""
    
    def __init__(self, grid, num_firefighters=1, max_steps=300, algorithm="astar"):
        super().__init__()
        
        self.grid = grid
        self.num_firefighters = num_firefighters
        self.max_steps = max_steps
        self.algorithm = algorithm
        
        # Initialize firefighters
        self.grid = initialize_firefighters(self.grid, num_firefighters, algorithm=algorithm)
        
        # Metrics
        self.metrics = SimulationMetrics()
        self.total_people = np.sum(self.grid == PERSON) + np.sum(self.grid == PERSON_DANGER)
        self.metrics.initial_people_count = self.total_people
        
        # Simulation state
        self.step = 0
        self.paused = False
        self.speed = 1.0
        self.simulation_active = True
        self.end_reason = ""
        
        # Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_simulation)
        self.timer.start(120)
        
        # UI Setup
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI"""
        self.setWindowTitle("🚒 AI Firefighter Rescue Simulation 🔥")
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a1a;
            }
            QLabel {
                color: #ffffff;
                font-family: 'Courier New';
            }
            QPushButton {
                background-color: #333333;
                color: #ffffff;
                border: 1px solid #555555;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #444444;
            }
            QPushButton:pressed {
                background-color: #222222;
            }
            QSlider::groove:horizontal {
                background-color: #333333;
                height: 8px;
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background-color: #ff9600;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
        """)
        
        # Main widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # Layout
        main_layout = QHBoxLayout(main_widget)
        
        # Left side - Grid canvas
        self.canvas = GridCanvas(self.grid)
        main_layout.addWidget(self.canvas, 2)
        
        # Right side - Controls and stats
        right_layout = QVBoxLayout()
        
        # Title
        title = QLabel("SIMULATION")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        right_layout.addWidget(title)
        
        # Stats panel
        self.stats_label = QLabel()
        self.stats_label.setFont(QFont('Courier New', 11))
        self.update_stats()
        right_layout.addWidget(self.stats_label)
        
        # Controls
        right_layout.addSpacing(20)
        
        controls_label = QLabel("CONTROLS")
        controls_font = QFont()
        controls_font.setPointSize(12)
        controls_font.setBold(True)
        controls_label.setFont(controls_font)
        right_layout.addWidget(controls_label)
        
        # Pause button
        self.pause_btn = QPushButton("⏸ PAUSE")
        self.pause_btn.clicked.connect(self.toggle_pause)
        right_layout.addWidget(self.pause_btn)
        
        # Speed label and slider
        speed_label = QLabel("Speed:")
        right_layout.addWidget(speed_label)
        
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setMinimum(1)
        self.speed_slider.setMaximum(5)
        self.speed_slider.setValue(2)
        self.speed_slider.setTickPosition(QSlider.TicksBelow)
        self.speed_slider.setTickInterval(1)
        self.speed_slider.valueChanged.connect(self.update_speed)
        right_layout.addWidget(self.speed_slider)
        
        self.speed_value_label = QLabel("1.0x")
        right_layout.addWidget(self.speed_value_label)
        
        right_layout.addSpacing(10)
        
        # Reset button
        reset_btn = QPushButton("🔄 RESET")
        reset_btn.clicked.connect(self.reset_simulation)
        right_layout.addWidget(reset_btn)
        
        # Exit button
        exit_btn = QPushButton("❌ EXIT")
        exit_btn.clicked.connect(self.close)
        right_layout.addWidget(exit_btn)
        
        right_layout.addStretch()
        
        # Add right layout to main
        main_layout.addLayout(right_layout, 1)
        
        # Window size
        self.setGeometry(100, 100, 1600, 900)
        self.show()
    
    def update_simulation(self):
        """Update simulation state"""
        if self.simulation_active and not self.paused:
            # Update based on speed
            self.step += self.speed # Smooth speed scaling

            # Move firefighters
            self.grid = spread_fire(self.grid, int(self.step))
            self.grid = move_firefighter(self.grid)
                
            # Update metrics
            stats = self.metrics.update(self.grid)
            ff_stats = get_firefighter_stats(self.grid)
            self.metrics.people_rescued = ff_stats.get('rescued', 0)
                
            # Check end conditions
            people_safe = stats['safe']
            people_danger = stats['danger']
                
            if people_safe == 0 and people_danger == 0:
                self.metrics.people_rescued = self.total_people
                self.simulation_active = False
                self.end_reason = "✅ All People Rescued!"
                
            if int(self.step) >= self.max_steps:
                self.metrics.people_burned = people_safe + people_danger
                self.simulation_active = False
                self.end_reason = "⏱️ Max Steps Reached"
        
        # Update canvas and stats
        self.canvas.update_grid(self.grid)
        self.update_stats()
    
    def update_stats(self):
        """Update statistics display"""
        stats_text = f"""
Step: {int(self.step)}/{self.max_steps}

Rescued: {self.metrics.people_rescued}/{self.total_people}
Success: {(self.metrics.people_rescued/self.total_people*100):.1f}%

Fire Cells: {np.sum(self.grid == FIRE)}

Algorithm: {self.algorithm.upper()}
Speed: {self.speed:.1f}x

Status: {'PAUSED' if self.paused else 'RUNNING'}

{self.end_reason}
        """
        self.stats_label.setText(stats_text)
    
    def toggle_pause(self):
        """Toggle pause"""
        self.paused = not self.paused
        self.pause_btn.setText("▶ RESUME" if self.paused else "⏸ PAUSE")
    
    def update_speed(self, value):
        """Update speed from slider"""
        speeds = {1: 0.5, 2: 1.0, 3: 1.5, 4: 2.0, 5: 3.0}
        self.speed = speeds.get(value, 1.0)
        self.speed_value_label.setText(f"{self.speed:.1f}x")
    
    def reset_simulation(self):
        """Reset simulation"""
        from environment import create_environment
        
        self.grid = create_environment()
        self.grid = initialize_firefighters(self.grid, self.num_firefighters, algorithm=self.algorithm)
        self.step = 0
        self.paused = False
        self.simulation_active = True
        self.end_reason = ""
        self.metrics = SimulationMetrics()
        self.metrics.initial_people_count = self.total_people
    
    def closeEvent(self, event):
        """Handle window close"""
        self.timer.stop()
        
        # Print final report
        ff_stats = get_firefighter_stats(self.grid)
        self.metrics.print_report(self.total_people, ff_stats)
        
        event.accept()


def run_simulation(grid, num_firefighters=1, max_steps=300, algorithm="astar", **kwargs):
    """Entry point for simulation"""
    app = QApplication(sys.argv)
    sim = PyQt5Simulation(grid, num_firefighters, max_steps, algorithm)
    sys.exit(app.exec_())