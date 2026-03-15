"""
dashboard.py — PyQt5 Desktop Dashboard for Zerodha Momentum Bot
================================================================
Run from inside the zerodha_momentum_bot folder:
    python dashboard.py

Requirements:
    pip install PyQt5 pyqtgraph kiteconnect pandas numpy
"""

import os
import sys
import csv
import json
import threading
import logging
from datetime import datetime, date
import numpy as np
import pandas as pd

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QTabWidget, QFrame, QSplitter, QTextEdit, QHeaderView, QMessageBox,
    QSizePolicy, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox,
    QCheckBox, QGroupBox, QScrollArea, QProgressBar
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread
from PyQt5.QtGui import QFont, QColor, QPalette
import pyqtgraph as pg

# Add bot folder to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from login import get_kite_client
from signals import fetch_nifty50, is_market_bullish
from orders import get_current_holdings, get_current_prices, get_portfolio_value

# ═══════════════════════════════════════════════════════
# COLOURS — Dark theme matching the backtest charts
# ═══════════════════════════════════════════════════════

C_BG      = "#050a0f"
C_PANEL   = "#070d14"
C_BORDER  = "#0d2535"
C_TEXT    = "#cce8ff"
C_SUBTEXT = "#4a7a9b"
C_ACCENT  = "#00d4ff"
C_GREEN   = "#00ff9d"
C_RED     = "#ff2d5e"
C_YELLOW  = "#ffd600"
C_PURPLE  = "#b44dff"
C_BULL    = "#00ff9d"
C_BEAR    = "#ff2d5e"

STYLE_SHEET = f"""
QMainWindow, QWidget {{
    background-color: {C_BG};
    color: {C_TEXT};
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 13px;
}}
QTabWidget::pane {{
    border: 1px solid {C_BORDER};
    background: {C_PANEL};
}}
QTabBar::tab {{
    background: {C_BG};
    color: {C_SUBTEXT};
    padding: 8px 22px;
    border: 1px solid {C_ACCENT}33;
    border-bottom: none;
    font-size: 11px;
    letter-spacing: 1px;
}}
QTabBar::tab:selected {{
    background: {C_PANEL};
    color: {C_ACCENT};
    border-top: 2px solid {C_ACCENT};
}}
QTabBar::tab:hover {{
    color: {C_TEXT};
    background: #0a1520;
}}
QPushButton {{
    background-color: transparent;
    color: {C_ACCENT};
    border: 1px solid {C_ACCENT};
    border-radius: 2px;
    padding: 7px 16px;
    font-size: 11px;
    letter-spacing: 1px;
    font-family: 'Consolas', monospace;
}}
QPushButton:hover  {{ background-color: {C_ACCENT}22; color: #ffffff; }}
QPushButton:pressed {{ background-color: {C_ACCENT}44; }}
QPushButton:disabled {{ color: {C_SUBTEXT}; border-color: {C_BORDER}; }}
QTableWidget {{
    background-color: {C_PANEL};
    alternate-background-color: #1a1f27;
    color: {C_TEXT};
    gridline-color: {C_BORDER};
    border: 1px solid {C_BORDER};
    border-radius: 4px;
}}
QTableWidget::item {{ padding: 6px 10px; }}
QHeaderView::section {{
    background-color: #030810;
    color: {C_ACCENT};
    padding: 8px;
    border: 1px solid {C_ACCENT}44;
    font-weight: bold;
    font-size: 11px;
    letter-spacing: 1px;
}}
QTextEdit {{
    background-color: {C_PANEL};
    color: #00ff9d;
    border: 1px solid {C_BORDER};
    border-radius: 4px;
    font-family: 'Consolas', monospace;
    font-size: 11px;
}}
QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    color: {C_BORDER};
}}
QScrollBar:vertical {{
    background: {C_BG};
    width: 5px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {C_ACCENT}66;
    border-radius: 2px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {C_ACCENT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: #060d16;
    color: {C_ACCENT};
    border: 1px solid {C_ACCENT}55;
    border-radius: 2px;
    padding: 5px 8px;
    font-size: 12px;
    font-family: 'Consolas', monospace;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {C_ACCENT};
    background: #081525;
}}
QGroupBox {{
    color: {C_ACCENT};
    border: 1px solid {C_ACCENT}55;
    border-radius: 2px;
    margin-top: 10px;
    padding-top: 10px;
    font-weight: bold;
    font-size: 11px;
    letter-spacing: 2px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {C_ACCENT};
}}
QCheckBox {{
    color: {C_TEXT};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {C_BORDER};
    border-radius: 3px;
    background: {C_BG};
}}
QCheckBox::indicator:checked {{
    background: {C_ACCENT};
    border-color: {C_ACCENT};
}}
QProgressBar {{
    background: {C_BG};
    border: 1px solid {C_ACCENT}44;
    border-radius: 2px;
    text-align: center;
    color: {C_ACCENT};
    height: 14px;
    font-family: 'Consolas', monospace;
    font-size: 10px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {C_ACCENT}66, stop:1 {C_ACCENT});
    border-radius: 1px;
}}
"""


# ═══════════════════════════════════════════════════════
# WORKER SIGNALS
# ═══════════════════════════════════════════════════════

class WorkerSignals(QObject):
    finished  = pyqtSignal(object)
    error     = pyqtSignal(str)
    log       = pyqtSignal(str)


class Worker(QThread):
    """Generic background worker — runs a function in a thread."""
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn      = fn
        self.args    = args
        self.kwargs  = kwargs
        self.signals = WorkerSignals()

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))


# ═══════════════════════════════════════════════════════
# STAT CARD WIDGET
# ═══════════════════════════════════════════════════════

class StatCard(QFrame):
    def __init__(self, title, value="—", color=C_ACCENT):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setFixedHeight(80)
        self.setMinimumWidth(155)
        self._color = color
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #080f18, stop:1 #050a0f);
                border: 1px solid {C_ACCENT}44;
                border-left: 2px solid {C_ACCENT};
                border-radius: 0px;
                padding: 0px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(12, 8, 12, 8)

        self.title_lbl = QLabel(title.upper())
        self.title_lbl.setStyleSheet(
            f"color: {C_SUBTEXT}; font-size: 9px; letter-spacing: 2px;"
            f"font-family: 'Consolas', monospace; border: none;")

        self.value_lbl = QLabel(value)
        self.value_lbl.setStyleSheet(
            f"color: {color}; font-size: 20px; font-weight: bold;"
            f"font-family: 'Consolas', monospace; border: none;")

        layout.addWidget(self.title_lbl)
        layout.addWidget(self.value_lbl)

    def set_value(self, value, color=None):
        self.value_lbl.setText(str(value))
        c = color or self._color
        self.value_lbl.setStyleSheet(
            f"color: {c}; font-size: 20px; font-weight: bold;"
            f"font-family: 'Consolas', monospace; border: none;")


# ═══════════════════════════════════════════════════════
# REGIME WIDGET
# ═══════════════════════════════════════════════════════

class RegimeWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setFixedHeight(80)
        self.setMinimumWidth(260)
        self.setMaximumWidth(340)
        self._bullish = None
        self.setStyleSheet(f"""
            QFrame {{
                background: #080f18;
                border: 1px solid {C_ACCENT}44;
                border-left: 2px solid {C_ACCENT};
                border-radius: 0px;
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 8, 16, 8)

        left = QWidget()
        left.setStyleSheet("background: transparent; border: none;")
        ll = QVBoxLayout(left)
        ll.setSpacing(1)
        ll.setContentsMargins(0,0,0,0)

        lbl_title = QLabel("REGIME")
        lbl_title.setStyleSheet(
            f"color: {C_SUBTEXT}; font-size: 9px; letter-spacing: 2px;"
            f"font-family: 'Consolas', monospace; border: none;")

        self.status_lbl = QLabel("UNKNOWN")
        self.status_lbl.setStyleSheet(
            f"color: {C_SUBTEXT}; font-size: 22px; font-weight: bold;"
            f"letter-spacing: 2px; font-family: 'Consolas', monospace; border: none;")

        ll.addWidget(lbl_title)
        ll.addWidget(self.status_lbl)

        right = QWidget()
        right.setStyleSheet("background: transparent; border: none;")
        rl = QVBoxLayout(right)
        rl.setSpacing(3)
        rl.setContentsMargins(0,0,0,0)

        lbl_n50 = QLabel("NIFTY 50")
        lbl_n50.setStyleSheet(
            f"color: {C_SUBTEXT}; font-size: 9px; letter-spacing: 1px;"
            f"font-family: 'Consolas', monospace; border: none;")

        self.nifty_lbl = QLabel("—")
        self.nifty_lbl.setStyleSheet(
            f"color: {C_TEXT}; font-size: 14px; font-weight: bold;"
            f"font-family: 'Consolas', monospace; border: none;")

        self.detail_lbl = QLabel("Connect to check")
        self.detail_lbl.setStyleSheet(
            f"color: {C_SUBTEXT}; font-size: 10px; letter-spacing: 1px;"
            f"font-family: 'Consolas', monospace; border: none;")

        rl.addWidget(lbl_n50)
        rl.addWidget(self.nifty_lbl)
        rl.addWidget(self.detail_lbl)

        layout.addWidget(left)
        layout.addWidget(right)

    def set_regime(self, bullish: bool, nifty: float, ema: float):
        self._bullish = bullish
        if bullish:
            self.status_lbl.setText("BULLISH")
            self.status_lbl.setStyleSheet(
                f"color: {C_BULL}; font-size: 22px; font-weight: bold;"
                f"letter-spacing: 2px; font-family: 'Consolas', monospace; border: none;")
            self.setStyleSheet(f"""
                QFrame {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #051a0f, stop:1 #080f18);
                    border: 1px solid {C_BULL}66;
                    border-left: 2px solid {C_BULL};
                    border-radius: 0px;
                }}
            """)
        else:
            self.status_lbl.setText("BEARISH")
            self.status_lbl.setStyleSheet(
                f"color: {C_BEAR}; font-size: 22px; font-weight: bold;"
                f"letter-spacing: 2px; font-family: 'Consolas', monospace; border: none;")
            self.setStyleSheet(f"""
                QFrame {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #1a0508, stop:1 #080f18);
                    border: 1px solid {C_BEAR}66;
                    border-left: 2px solid {C_BEAR};
                    border-radius: 0px;
                }}
            """)
        self.nifty_lbl.setText(f"{nifty:,.0f}")
        self.detail_lbl.setText(f"EMA {config.EMA_WINDOW}: {ema:,.0f}")


# ═══════════════════════════════════════════════════════
# MAIN DASHBOARD
# ═══════════════════════════════════════════════════════

class Dashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.kite        = None
        self.bot_thread  = None
        self.bot_running = False

        self.setWindowTitle("Zerodha Momentum Bot — Dashboard")
        self.setMinimumSize(1280, 800)
        self._apply_theme()
        self._build_ui()

        # Auto-refresh timer (every 60 seconds)
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._refresh_data)
        self.refresh_timer.start(60_000)

        # Try to connect on startup
        QTimer.singleShot(500, self._connect)

    def _apply_theme(self):
        self.setStyleSheet(STYLE_SHEET)
        pg.setConfigOption("background", C_BG)
        pg.setConfigOption("foreground", C_TEXT)

    # ─────────────────────────────────────────────
    # UI CONSTRUCTION
    # ─────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        # ── Header ──
        root.addWidget(self._build_header())

        # ── Stat Cards ──
        root.addLayout(self._build_stat_cards())

        # ── Main content tabs ──
        tabs = QTabWidget()
        tabs.addTab(self._build_portfolio_tab(),  "Portfolio")
        tabs.addTab(self._build_chart_tab(),      "Equity Curve")
        tabs.addTab(self._build_tradelog_tab(),   "Trade Log")
        tabs.addTab(self._build_log_tab(),        "Bot Log")
        tabs.addTab(self._build_config_tab(),     "Config")
        tabs.addTab(self._build_backtest_tab(),   "Backtest")
        root.addWidget(tabs)

        # ── Bottom controls ──
        root.addLayout(self._build_controls())

    def _build_header(self):
        frame = QFrame()
        frame.setFixedHeight(56)
        frame.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #050a0f, stop:0.5 #071525, stop:1 #050a0f);
                border-bottom: 1px solid {C_ACCENT}66;
                border-top: none;
                border-left: none;
                border-right: none;
                padding: 0px 16px;
            }}
        """)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(16, 0, 16, 0)

        # Decorative left accent bar
        accent_bar = QFrame()
        accent_bar.setFixedSize(4, 32)
        accent_bar.setStyleSheet(f"background: {C_ACCENT}; border: none;")

        title = QLabel("ZERODHA MOMENTUM BOT")
        title.setStyleSheet(
            f"color: {C_ACCENT}; font-size: 16px; font-weight: bold;"
            f"letter-spacing: 3px; font-family: 'Consolas', monospace; border: none;")

        separator = QLabel("//")
        separator.setStyleSheet(f"color: {C_ACCENT}44; font-size: 14px; border: none;")

        subtitle = QLabel("NIFTY 500 | CROSS-SECTIONAL MOMENTUM | EMA REGIME FILTER")
        subtitle.setStyleSheet(
            f"color: {C_SUBTEXT}; font-size: 10px; letter-spacing: 2px;"
            f"font-family: 'Consolas', monospace; border: none;")

        self.last_refresh_lbl = QLabel("")
        self.last_refresh_lbl.setStyleSheet(
            f"color: {C_SUBTEXT}; font-size: 10px; letter-spacing: 1px; border: none;")

        self.conn_lbl = QLabel("[ DISCONNECTED ]")
        self.conn_lbl.setStyleSheet(
            f"color: {C_SUBTEXT}; font-size: 11px; padding: 4px 12px;"
            f"border: 1px solid {C_SUBTEXT}55; letter-spacing: 1px;"
            f"font-family: 'Consolas', monospace;")

        layout.addWidget(accent_bar)
        layout.addSpacing(10)
        layout.addWidget(title)
        layout.addSpacing(8)
        layout.addWidget(separator)
        layout.addSpacing(8)
        layout.addWidget(subtitle)
        layout.addStretch()
        layout.addWidget(self.last_refresh_lbl)
        layout.addSpacing(12)
        layout.addWidget(self.conn_lbl)
        return frame

    def _build_stat_cards(self):
        layout = QHBoxLayout()
        layout.setSpacing(8)

        self.card_value    = StatCard("Portfolio Value",    "—",  C_ACCENT)
        self.card_pnl      = StatCard("Day P&L",            "—",  C_SUBTEXT)
        self.card_holdings = StatCard("Holdings",           "—",  C_YELLOW)
        self.card_cash     = StatCard("Cash",               "—",  C_SUBTEXT)
        self.regime_widget = RegimeWidget()

        for card in [self.card_value, self.card_pnl,
                     self.card_holdings, self.card_cash]:
            layout.addWidget(card, stretch=1)
        layout.addWidget(self.regime_widget, stretch=0)
        layout.addStretch()
        return layout

    def _build_portfolio_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 8, 0, 0)

        self.portfolio_table = QTableWidget()
        self.portfolio_table.setColumnCount(6)
        self.portfolio_table.setHorizontalHeaderLabels(
            ["Symbol", "Quantity", "Avg Price", "LTP", "Current Value", "P&L"])
        self.portfolio_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self.portfolio_table.setAlternatingRowColors(True)
        self.portfolio_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.portfolio_table.verticalHeader().setVisible(False)

        layout.addWidget(self.portfolio_table)
        return widget

    def _build_chart_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 8, 0, 0)

        # pyqtgraph plot
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel("left",   "Portfolio Value (Rs)")
        self.plot_widget.setLabel("bottom", "Date")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setBackground(C_PANEL)

        layout.addWidget(self.plot_widget)
        self._load_equity_curve()
        return widget

    def _build_tradelog_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 8, 0, 0)

        self.trade_table = QTableWidget()
        self.trade_table.setColumnCount(6)
        self.trade_table.setHorizontalHeaderLabels(
            ["Timestamp", "Symbol", "Action", "Quantity", "Order ID", "Status"])
        self.trade_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self.trade_table.setAlternatingRowColors(True)
        self.trade_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.trade_table.verticalHeader().setVisible(False)

        layout.addWidget(self.trade_table)
        self._load_trade_log()
        return widget

    def _build_log_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 8, 0, 0)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.NoWrap)

        btn_refresh_log = QPushButton("Refresh Log")
        btn_refresh_log.clicked.connect(self._load_bot_log)

        layout.addWidget(self.log_text)
        layout.addWidget(btn_refresh_log)
        self._load_bot_log()
        return widget


    # ─────────────────────────────────────────────
    # CONFIG TAB
    # ─────────────────────────────────────────────

    def _build_config_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        scroll.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # API Credentials
        grp_api = QGroupBox("Kite API Credentials")
        api_lay = QGridLayout(grp_api)
        api_lay.setSpacing(8)

        self.cfg_api_key    = QLineEdit(getattr(config, "KITE_API_KEY", ""))
        self.cfg_api_secret = QLineEdit(getattr(config, "KITE_API_SECRET", ""))
        self.cfg_api_secret.setEchoMode(QLineEdit.Password)
        self.cfg_user_id    = QLineEdit(getattr(config, "ZERODHA_USER_ID", ""))
        self.cfg_password   = QLineEdit(getattr(config, "ZERODHA_PASSWORD", ""))
        self.cfg_password.setEchoMode(QLineEdit.Password)
        self.cfg_totp       = QLineEdit(getattr(config, "ZERODHA_TOTP_SECRET", ""))
        self.cfg_totp.setEchoMode(QLineEdit.Password)

        for row, (lbl, w) in enumerate([
            ("API Key",     self.cfg_api_key),
            ("API Secret",  self.cfg_api_secret),
            ("User ID",     self.cfg_user_id),
            ("Password",    self.cfg_password),
            ("TOTP Secret", self.cfg_totp),
        ]):
            api_lay.addWidget(QLabel(lbl), row, 0)
            api_lay.addWidget(w, row, 1)

        # Strategy Parameters
        grp_strat = QGroupBox("Strategy Parameters")
        strat_lay = QGridLayout(grp_strat)
        strat_lay.setSpacing(8)

        self.cfg_capital    = QSpinBox()
        self.cfg_capital.setRange(10000, 100_000_000)
        self.cfg_capital.setSingleStep(100000)
        self.cfg_capital.setValue(getattr(config, "TOTAL_CAPITAL", 1_000_000))

        self.cfg_top_n      = QSpinBox()
        self.cfg_top_n.setRange(1, 100)
        self.cfg_top_n.setValue(getattr(config, "TOP_N", 30))

        self.cfg_exit_rank  = QSpinBox()
        self.cfg_exit_rank.setRange(1, 100)
        self.cfg_exit_rank.setValue(getattr(config, "EXIT_RANK", 34))

        self.cfg_mom_window = QSpinBox()
        self.cfg_mom_window.setRange(50, 500)
        self.cfg_mom_window.setValue(getattr(config, "MOMENTUM_WINDOW", 252))

        self.cfg_ema_window = QSpinBox()
        self.cfg_ema_window.setRange(10, 500)
        self.cfg_ema_window.setValue(getattr(config, "EMA_WINDOW", 200))

        self.cfg_max_dd     = QDoubleSpinBox()
        self.cfg_max_dd.setRange(1.0, 50.0)
        self.cfg_max_dd.setSingleStep(1.0)
        self.cfg_max_dd.setValue(getattr(config, "MAX_DRAWDOWN_PCT", 20.0))

        self.cfg_min_price  = QSpinBox()
        self.cfg_min_price.setRange(1, 10000)
        self.cfg_min_price.setValue(getattr(config, "MIN_STOCK_PRICE", 50))

        for row, (lbl, w) in enumerate([
            ("Total Capital (Rs)",     self.cfg_capital),
            ("Top N Stocks",           self.cfg_top_n),
            ("Exit Rank",              self.cfg_exit_rank),
            ("Momentum Window (days)", self.cfg_mom_window),
            ("EMA Window",             self.cfg_ema_window),
            ("Max Drawdown % (kill)",  self.cfg_max_dd),
            ("Min Stock Price (Rs)",   self.cfg_min_price),
        ]):
            strat_lay.addWidget(QLabel(lbl), row, 0)
            strat_lay.addWidget(w, row, 1)

        # Telegram
        grp_tg = QGroupBox("Telegram Alerts (optional)")
        tg_lay = QGridLayout(grp_tg)
        tg_lay.setSpacing(8)
        self.cfg_tg_token   = QLineEdit(getattr(config, "TELEGRAM_BOT_TOKEN", ""))
        self.cfg_tg_chat_id = QLineEdit(getattr(config, "TELEGRAM_CHAT_ID", ""))
        tg_lay.addWidget(QLabel("Bot Token"), 0, 0)
        tg_lay.addWidget(self.cfg_tg_token, 0, 1)
        tg_lay.addWidget(QLabel("Chat ID"), 1, 0)
        tg_lay.addWidget(self.cfg_tg_chat_id, 1, 1)

        # Scheduler
        grp_sched = QGroupBox("Scheduler")
        sched_lay = QGridLayout(grp_sched)
        sched_lay.setSpacing(8)
        self.cfg_reb_hour = QSpinBox()
        self.cfg_reb_hour.setRange(0, 23)
        self.cfg_reb_hour.setValue(getattr(config, "REBALANCE_HOUR", 9))
        self.cfg_reb_min  = QSpinBox()
        self.cfg_reb_min.setRange(0, 59)
        self.cfg_reb_min.setValue(getattr(config, "REBALANCE_MINUTE", 30))
        sched_lay.addWidget(QLabel("Rebalance Hour (IST)"), 0, 0)
        sched_lay.addWidget(self.cfg_reb_hour, 0, 1)
        sched_lay.addWidget(QLabel("Rebalance Minute"), 1, 0)
        sched_lay.addWidget(self.cfg_reb_min, 1, 1)

        btn_save = QPushButton("Save Config")
        btn_save.setStyleSheet(
            f"background: #0d2818; color: {C_GREEN};"
            f"border: 1px solid {C_GREEN}; border-radius: 6px; padding: 8px 18px;")
        btn_save.clicked.connect(self._save_config)

        self.cfg_status_lbl = QLabel("")
        self.cfg_status_lbl.setStyleSheet(f"color: {C_GREEN}; font-size: 11px;")
        self.cfg_status_lbl.setAlignment(Qt.AlignCenter)

        for w in [grp_api, grp_strat, grp_tg, grp_sched,
                  btn_save, self.cfg_status_lbl]:
            layout.addWidget(w)
        layout.addStretch()
        return scroll

    def _save_config(self):
        try:
            cfg_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "config.py")
            with open(cfg_path, "r") as f:
                lines = f.readlines()

            def update(lines, key, value):
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if stripped.startswith(key) and "=" in stripped:
                        indent = line[:len(line) - len(line.lstrip())]
                        if isinstance(value, str):
                            lines[i] = indent + f'{key:<24}= "{value}"\n'
                        else:
                            lines[i] = indent + f'{key:<24}= {value}\n'
                        return

            update(lines, "KITE_API_KEY",       self.cfg_api_key.text())
            update(lines, "KITE_API_SECRET",     self.cfg_api_secret.text())
            update(lines, "ZERODHA_USER_ID",     self.cfg_user_id.text())
            update(lines, "ZERODHA_PASSWORD",    self.cfg_password.text())
            update(lines, "ZERODHA_TOTP_SECRET", self.cfg_totp.text())
            update(lines, "TOTAL_CAPITAL",       self.cfg_capital.value())
            update(lines, "TOP_N",               self.cfg_top_n.value())
            update(lines, "EXIT_RANK",           self.cfg_exit_rank.value())
            update(lines, "MOMENTUM_WINDOW",     self.cfg_mom_window.value())
            update(lines, "EMA_WINDOW",          self.cfg_ema_window.value())
            update(lines, "MAX_DRAWDOWN_PCT",    self.cfg_max_dd.value())
            update(lines, "MIN_STOCK_PRICE",     self.cfg_min_price.value())
            update(lines, "TELEGRAM_BOT_TOKEN",  self.cfg_tg_token.text())
            update(lines, "TELEGRAM_CHAT_ID",    self.cfg_tg_chat_id.text())
            update(lines, "REBALANCE_HOUR",      self.cfg_reb_hour.value())
            update(lines, "REBALANCE_MINUTE",    self.cfg_reb_min.value())

            with open(cfg_path, "w") as f:
                f.writelines(lines)

            import importlib
            importlib.reload(config)

            self.cfg_status_lbl.setStyleSheet(f"color: {C_GREEN}; font-size: 11px;")
            self.cfg_status_lbl.setText("Saved. Restart bot scheduler to apply changes.")
            self._log("Config saved to config.py")

        except Exception as e:
            self.cfg_status_lbl.setStyleSheet(f"color: {C_RED}; font-size: 11px;")
            self.cfg_status_lbl.setText(f"Save failed: {e}")
            self._log(f"Config save failed: {e}")

    # ─────────────────────────────────────────────
    # BACKTEST TAB
    # ─────────────────────────────────────────────

    def _build_backtest_tab(self):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)

        # Left: controls
        left = QWidget()
        left.setFixedWidth(260)
        ll = QVBoxLayout(left)
        ll.setSpacing(10)

        grp = QGroupBox("Backtest Settings")
        grp_lay = QGridLayout(grp)
        grp_lay.setSpacing(8)

        self.bt_start_date = QLineEdit("2021-01-01")
        self.bt_capital    = QSpinBox()
        self.bt_capital.setRange(10000, 100_000_000)
        self.bt_capital.setSingleStep(100000)
        self.bt_capital.setValue(getattr(config, "TOTAL_CAPITAL", 1_000_000))
        self.bt_top_n      = QSpinBox()
        self.bt_top_n.setRange(1, 100)
        self.bt_top_n.setValue(30)
        self.bt_exit_rank  = QSpinBox()
        self.bt_exit_rank.setRange(1, 100)
        self.bt_exit_rank.setValue(34)

        for row, (lbl, w) in enumerate([
            ("Start Date",   self.bt_start_date),
            ("Capital (Rs)", self.bt_capital),
            ("Top N",        self.bt_top_n),
            ("Exit Rank",    self.bt_exit_rank),
        ]):
            grp_lay.addWidget(QLabel(lbl), row, 0)
            grp_lay.addWidget(w, row, 1)

        grp_f = QGroupBox("Regime Filters")
        fl    = QVBoxLayout(grp_f)
        self.bt_filter_none = QCheckBox("No Filter")
        self.bt_filter_50   = QCheckBox("EMA 50")
        self.bt_filter_100  = QCheckBox("EMA 100")
        self.bt_filter_200  = QCheckBox("EMA 200")
        self.bt_filter_200.setChecked(True)
        for cb in [self.bt_filter_none, self.bt_filter_50,
                   self.bt_filter_100, self.bt_filter_200]:
            fl.addWidget(cb)

        self.bt_progress   = QProgressBar()
        self.bt_progress.setRange(0, 0)
        self.bt_progress.setVisible(False)

        self.btn_run_bt    = QPushButton("Run Backtest")
        self.btn_run_bt.setStyleSheet(
            f"background: #1f3a5f; color: {C_ACCENT};"
            f"border: 1px solid {C_ACCENT}; border-radius: 6px; padding: 8px;")
        self.btn_run_bt.clicked.connect(self._run_backtest)

        self.bt_status_lbl = QLabel("Configure and click Run")
        self.bt_status_lbl.setStyleSheet(f"color: {C_SUBTEXT}; font-size: 11px;")
        self.bt_status_lbl.setWordWrap(True)

        for w in [grp, grp_f, self.btn_run_bt,
                  self.bt_progress, self.bt_status_lbl]:
            ll.addWidget(w)
        ll.addStretch()

        # Right: results
        right  = QWidget()
        rl     = QVBoxLayout(right)
        rl.setSpacing(8)

        self.bt_stats_table = QTableWidget()
        self.bt_stats_table.setAlternatingRowColors(True)
        self.bt_stats_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.bt_stats_table.setFixedHeight(300)
        self.bt_stats_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)

        self.bt_plot = pg.PlotWidget()
        self.bt_plot.setLabel("left",   "Portfolio Value (Rs)")
        self.bt_plot.setLabel("bottom", "Days")
        self.bt_plot.showGrid(x=True, y=True, alpha=0.3)
        self.bt_plot.setBackground(C_PANEL)
        self.bt_plot.addLegend()

        rl.addWidget(QLabel("Performance Comparison"))
        rl.addWidget(self.bt_stats_table)
        rl.addWidget(self.bt_plot)

        layout.addWidget(left)
        layout.addWidget(right)
        return widget

    def _run_backtest(self):
        if not self.kite:
            QMessageBox.warning(self, "Not Connected",
                                "Please connect to Kite first.")
            return

        filters = {}
        if self.bt_filter_none.isChecked(): filters["No Filter"] = None
        if self.bt_filter_50.isChecked():   filters["EMA 50"]    = 50
        if self.bt_filter_100.isChecked():  filters["EMA 100"]   = 100
        if self.bt_filter_200.isChecked():  filters["EMA 200"]   = 200

        if not filters:
            QMessageBox.warning(self, "No Filter", "Select at least one regime filter.")
            return

        start_date = self.bt_start_date.text().strip()
        capital    = self.bt_capital.value()
        top_n      = self.bt_top_n.value()
        exit_rank  = self.bt_exit_rank.value()

        self.btn_run_bt.setEnabled(False)
        self.bt_progress.setVisible(True)
        self.bt_status_lbl.setText("Downloading data from Kite...")

        kite = self.kite

        def do_backtest():
            # Import backtest module dynamically
            import importlib.util
            bt_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "..", "kite_backtest.py")
            spec = importlib.util.spec_from_file_location("kite_backtest", bt_path)
            bt   = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(bt)

            end_date = date.today().strftime("%Y-%m-%d")
            universe = bt.get_nifty500_universe()
            prices   = bt.download_prices(kite, universe, start_date, end_date)
            nifty50  = bt.download_nifty50(kite, start_date, end_date)
            nifty50  = nifty50.reindex(prices.index, method="ffill").dropna()

            results = []
            for label, ema_window in filters.items():
                weights       = bt.build_weights(prices, nifty50, ema_window)
                result        = bt.simulate(prices, weights, label)
                result["stats"] = bt.calc_stats(result)
                results.append(result)

            # Benchmark
            bench_ret    = nifty50.pct_change().fillna(0)
            bench_equity = (1 + bench_ret).cumprod() * capital
            bench_equity.name = "Nifty 50 B&H"
            bench = {"label": "Nifty 50 B&H", "equity": bench_equity,
                     "returns": bench_ret, "weights": pd.DataFrame()}
            bench["stats"] = bt.calc_stats(bench)
            results.append(bench)
            return results

        self.worker_bt = Worker(do_backtest)
        self.worker_bt.signals.finished.connect(self._on_backtest_done)
        self.worker_bt.signals.error.connect(self._on_backtest_error)
        self.worker_bt.start()

    def _on_backtest_done(self, results):
        self.btn_run_bt.setEnabled(True)
        self.bt_progress.setVisible(False)
        self.bt_status_lbl.setText("Backtest complete!")

        BT_COLORS = [C_ACCENT, C_GREEN, C_YELLOW, C_PURPLE, C_RED]

        # Plot equity curves
        self.bt_plot.clear()
        self.bt_plot.addLegend()
        capital = self.bt_capital.value()
        for i, res in enumerate(results):
            color  = BT_COLORS[i % len(BT_COLORS)]
            equity = res["equity"]
            x      = np.arange(len(equity))
            self.bt_plot.plot(x, equity.values,
                              pen=pg.mkPen(color=color, width=2),
                              name=res["label"])

        # Stats table
        metrics = ["CAGR", "Sharpe", "Sortino", "Max Drawdown",
                   "Calmar", "Win Rate", "Total Return",
                   "Final Value", "Ann. Volatility"]

        self.bt_stats_table.setColumnCount(len(results))
        self.bt_stats_table.setRowCount(len(metrics))
        self.bt_stats_table.setHorizontalHeaderLabels(
            [r["label"] for r in results])
        self.bt_stats_table.setVerticalHeaderLabels(metrics)
        self.bt_stats_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)

        for col, res in enumerate(results):
            for row, m in enumerate(metrics):
                val  = str(res["stats"].get(m, "-"))
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                if m == "CAGR":
                    item.setForeground(QColor(C_GREEN))
                elif m == "Max Drawdown":
                    item.setForeground(QColor(C_RED))
                self.bt_stats_table.setItem(row, col, item)

        self._log(f"Backtest complete — {len(results)} strategies")

    def _on_backtest_error(self, error):
        self.btn_run_bt.setEnabled(True)
        self.bt_progress.setVisible(False)
        self.bt_status_lbl.setText(f"Error: {error}")
        self._log(f"Backtest error: {error}")

    def _build_controls(self):
        layout = QHBoxLayout()
        layout.setSpacing(8)

        self.btn_connect   = QPushButton("Connect to Kite")
        self.btn_regime    = QPushButton("Check Regime")
        self.btn_refresh   = QPushButton("Refresh Portfolio")
        self.btn_dry_run   = QPushButton("Run Dry Run")
        self.btn_rebalance = QPushButton("Run Rebalance (LIVE)")
        self.btn_bot_start = QPushButton("Start Bot Scheduler")
        self.btn_bot_stop  = QPushButton("Stop Bot")

        self.btn_rebalance.setStyleSheet(
            f"background: #3d1515; color: {C_RED};"
            f"border: 1px solid {C_RED}; border-radius: 6px; padding: 8px 18px;")
        self.btn_bot_start.setStyleSheet(
            f"background: #0d2818; color: {C_GREEN};"
            f"border: 1px solid {C_GREEN}; border-radius: 6px; padding: 8px 18px;")
        self.btn_bot_stop.setEnabled(False)

        self.btn_connect.clicked.connect(self._connect)
        self.btn_regime.clicked.connect(self._check_regime)
        self.btn_refresh.clicked.connect(self._refresh_data)
        self.btn_dry_run.clicked.connect(self._run_dry_run)
        self.btn_rebalance.clicked.connect(self._run_rebalance)
        self.btn_bot_start.clicked.connect(self._start_bot)
        self.btn_bot_stop.clicked.connect(self._stop_bot)

        for btn in [self.btn_connect, self.btn_regime, self.btn_refresh,
                    self.btn_dry_run, self.btn_rebalance,
                    self.btn_bot_start, self.btn_bot_stop]:
            layout.addWidget(btn)

        return layout

    # ─────────────────────────────────────────────
    # CONNECT
    # ─────────────────────────────────────────────

    def _connect(self):
        self.conn_lbl.setText("[ CONNECTING... ]")
        self.conn_lbl.setStyleSheet(
            f"color: {C_YELLOW}; font-size: 11px; padding: 4px 12px;"
            f"border: 1px solid {C_YELLOW}88; letter-spacing: 1px;"
            f"font-family: 'Consolas', monospace;")

        def do_connect():
            return get_kite_client()

        self.worker = Worker(do_connect)
        self.worker.signals.finished.connect(self._on_connected)
        self.worker.signals.error.connect(self._on_connect_error)
        self.worker.start()

    def _on_connected(self, kite):
        self.kite = kite
        try:
            profile = kite.profile()
            name    = profile.get("user_name", "")
            self.conn_lbl.setText(f"[ {name.upper()} ]")
        except Exception:
            self.conn_lbl.setText("[ CONNECTED ]")
        self.conn_lbl.setStyleSheet(
            f"color: {C_GREEN}; font-size: 11px; padding: 4px 12px;"
            f"border: 1px solid {C_GREEN}88; letter-spacing: 1px;"
            f"font-family: 'Consolas', monospace;")
        self._log(f"Connected to Kite")
        self._refresh_data()
        self._check_regime()

    def _on_connect_error(self, error):
        self.conn_lbl.setText("[ DISCONNECTED ]")
        self.conn_lbl.setStyleSheet(
            f"color: {C_RED}; font-size: 11px; padding: 4px 12px;"
            f"border: 1px solid {C_RED}88; letter-spacing: 1px;"
            f"font-family: 'Consolas', monospace;")
        self._log(f"Connection failed: {error}")

    # ─────────────────────────────────────────────
    # REGIME CHECK
    # ─────────────────────────────────────────────

    def _check_regime(self):
        if not self.kite:
            self._log("Not connected to Kite")
            return

        def do_regime():
            nifty_prices = fetch_nifty50(self.kite, days=900)
            ema          = nifty_prices.ewm(
                span=config.EMA_WINDOW, adjust=False).mean()
            last_price   = float(nifty_prices.iloc[-1])
            last_ema     = float(ema.iloc[-1])
            bullish      = last_price > last_ema
            return bullish, last_price, last_ema

        self._log("Checking regime filter...")
        self.worker_regime = Worker(do_regime)
        self.worker_regime.signals.finished.connect(
            lambda r: self.regime_widget.set_regime(*r))
        self.worker_regime.signals.error.connect(
            lambda e: self._log(f"Regime check failed: {e}"))
        self.worker_regime.start()

    # ─────────────────────────────────────────────
    # REFRESH PORTFOLIO
    # ─────────────────────────────────────────────

    def _refresh_data(self):
        if not self.kite:
            return

        def do_refresh():
            holdings     = get_current_holdings(self.kite)
            port_value   = get_portfolio_value(self.kite)
            all_symbols  = list(holdings.keys())
            prices       = get_current_prices(self.kite, all_symbols) if all_symbols else {}
            positions    = self.kite.positions()
            return holdings, port_value, prices, positions

        self.worker_refresh = Worker(do_refresh)
        self.worker_refresh.signals.finished.connect(self._update_portfolio_ui)
        self.worker_refresh.signals.error.connect(
            lambda e: self._log(f"Refresh failed: {e}"))
        self.worker_refresh.start()

    def _update_portfolio_ui(self, data):
        holdings, port_value, prices, positions = data

        # Stat cards
        self.card_value.set_value(f"Rs {port_value/1e5:.2f}L", C_ACCENT)
        self.card_holdings.set_value(str(len(holdings)), C_YELLOW)

        # Day P&L from positions
        day_pnl = sum(
            p.get("day_m2m", 0) or 0
            for p in positions.get("net", [])
        )
        pnl_color = C_GREEN if day_pnl >= 0 else C_RED
        sign      = "+" if day_pnl >= 0 else ""
        self.card_pnl.set_value(f"{sign}Rs {day_pnl:,.0f}", pnl_color)

        # Portfolio table
        pos_map = {p["tradingsymbol"]: p
                   for p in positions.get("net", [])}

        self.portfolio_table.setRowCount(len(holdings))
        for row, (sym, qty) in enumerate(sorted(holdings.items())):
            pos       = pos_map.get(sym, {})
            avg_price = pos.get("average_price", 0) or 0
            ltp       = prices.get(sym, 0) or 0
            value     = ltp * qty
            pnl       = (ltp - avg_price) * qty

            items = [
                sym,
                str(qty),
                f"Rs {avg_price:,.2f}",
                f"Rs {ltp:,.2f}",
                f"Rs {value:,.0f}",
                f"Rs {pnl:+,.0f}",
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                if col == 5:  # P&L column
                    item.setForeground(
                        QColor(C_GREEN if pnl >= 0 else C_RED))
                self.portfolio_table.setItem(row, col, item)

        self.last_refresh_lbl.setText(
            f"Last refresh: {datetime.now().strftime('%H:%M:%S')}")
        self._log(f"Portfolio refreshed — {len(holdings)} holdings, "
                  f"value Rs {port_value/1e5:.2f}L")

    # ─────────────────────────────────────────────
    # EQUITY CURVE
    # ─────────────────────────────────────────────

    def _load_equity_curve(self):
        """Load portfolio snapshots from logs/portfolio.csv and plot."""
        try:
            log_file = config.PORTFOLIO_LOG_FILE
            if not os.path.exists(log_file):
                self._draw_placeholder_chart()
                return

            df = pd.read_csv(log_file)
            if "timestamp" not in df.columns or "total_value" not in df.columns:
                self._draw_placeholder_chart()
                return

            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.drop_duplicates("timestamp").sort_values("timestamp")

            x = np.arange(len(df))
            y = df["total_value"].values

            self.plot_widget.clear()
            pen = pg.mkPen(color=C_ACCENT, width=2)
            self.plot_widget.plot(x, y, pen=pen, name="Portfolio")

            # Add zero line reference
            self.plot_widget.addLine(
                y=config.TOTAL_CAPITAL,
                pen=pg.mkPen(color=C_SUBTEXT, width=1, style=Qt.DashLine))

            # X axis labels
            ticks = list(zip(
                x[::max(1, len(x)//8)].tolist(),
                df["timestamp"].dt.strftime("%b %y").iloc[
                    ::max(1, len(x)//8)].tolist()
            ))
            self.plot_widget.getAxis("bottom").setTicks([ticks])

        except Exception as e:
            self._draw_placeholder_chart()
            self._log(f"Could not load equity curve: {e}")

    def _draw_placeholder_chart(self):
        self.plot_widget.clear()
        text = pg.TextItem(
            "No portfolio history yet.\nRun a rebalance to start tracking.",
            color=C_SUBTEXT, anchor=(0.5, 0.5))
        self.plot_widget.addItem(text)
        text.setPos(0.5, 0.5)

    # ─────────────────────────────────────────────
    # TRADE LOG
    # ─────────────────────────────────────────────

    def _load_trade_log(self):
        try:
            log_file = config.ORDER_LOG_FILE
            if not os.path.exists(log_file):
                return

            with open(log_file, newline="") as f:
                reader  = csv.DictReader(f)
                rows    = list(reader)

            rows.reverse()  # newest first
            self.trade_table.setRowCount(len(rows))

            for r, row in enumerate(rows):
                action = row.get("transaction_type", "")
                items  = [
                    row.get("timestamp", "")[:19],
                    row.get("symbol", ""),
                    action,
                    row.get("quantity", ""),
                    row.get("order_id", ""),
                    row.get("status", ""),
                ]
                for c, text in enumerate(items):
                    item = QTableWidgetItem(text)
                    item.setTextAlignment(Qt.AlignCenter)
                    if c == 2:  # Action column
                        item.setForeground(
                            QColor(C_GREEN if action == "BUY" else C_RED))
                    self.trade_table.setItem(r, c, item)

        except Exception as e:
            self._log(f"Could not load trade log: {e}")

    # ─────────────────────────────────────────────
    # BOT LOG
    # ─────────────────────────────────────────────

    def _load_bot_log(self):
        try:
            log_file = config.BOT_LOG_FILE
            if not os.path.exists(log_file):
                self.log_text.setText("No log file found yet.")
                return
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            # Show last 200 lines
            self.log_text.setText("".join(lines[-200:]))
            # Scroll to bottom
            sb = self.log_text.verticalScrollBar()
            sb.setValue(sb.maximum())
        except Exception as e:
            self.log_text.setText(f"Could not read log: {e}")

    # ─────────────────────────────────────────────
    # BOT CONTROLS
    # ─────────────────────────────────────────────

    def _run_dry_run(self):
        if not self.kite:
            QMessageBox.warning(self, "Not Connected",
                                "Please connect to Kite first.")
            return
        self._log("Starting dry run...")
        self._run_bot_action(dry_run=True, force=True)

    def _run_rebalance(self):
        if not self.kite:
            QMessageBox.warning(self, "Not Connected",
                                "Please connect to Kite first.")
            return
        confirm = QMessageBox.question(
            self, "Confirm Live Rebalance",
            "This will place REAL orders on your Zerodha account.\n\nAre you sure?",
            QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            self._log("Starting LIVE rebalance...")
            self._run_bot_action(dry_run=False, force=True)

    def _run_bot_action(self, dry_run: bool, force: bool):
        def do_rebalance():
            from bot import run_rebalance
            run_rebalance(dry_run=dry_run, force=force)
            return "done"

        self.btn_dry_run.setEnabled(False)
        self.btn_rebalance.setEnabled(False)

        self.worker_bot = Worker(do_rebalance)
        self.worker_bot.signals.finished.connect(
            lambda _: self._on_action_done())
        self.worker_bot.signals.error.connect(
            lambda e: (self._log(f"Rebalance error: {e}"),
                       self._on_action_done()))
        self.worker_bot.start()

    def _on_action_done(self):
        self.btn_dry_run.setEnabled(True)
        self.btn_rebalance.setEnabled(True)
        self._load_trade_log()
        self._load_equity_curve()
        self._refresh_data()
        self._load_bot_log()
        self._log("Action complete.")

    def _start_bot(self):
        if self.bot_running:
            return
        if not self.kite:
            QMessageBox.warning(self, "Not Connected",
                                "Please connect to Kite first.")
            return

        self._log("Bot scheduler started — will rebalance on last trading day of month.")
        self.bot_running = True
        self.btn_bot_start.setEnabled(False)
        self.btn_bot_stop.setEnabled(True)

        def scheduler_loop():
            import schedule, time as _time
            run_time = f"{config.REBALANCE_HOUR:02d}:{config.REBALANCE_MINUTE:02d}"
            from bot import run_rebalance
            schedule.every().day.at(run_time).do(run_rebalance, dry_run=False)
            while self.bot_running:
                schedule.run_pending()
                _time.sleep(30)

        self.bot_thread = threading.Thread(
            target=scheduler_loop, daemon=True)
        self.bot_thread.start()

    def _stop_bot(self):
        self.bot_running = False
        self.btn_bot_start.setEnabled(True)
        self.btn_bot_stop.setEnabled(False)
        self._log("Bot scheduler stopped.")

    # ─────────────────────────────────────────────
    # LOGGING HELPER
    # ─────────────────────────────────────────────

    def _log(self, msg: str):
        ts  = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self.log_text.append(line)
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())


# ═══════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    win = Dashboard()
    win.show()

    sys.exit(app.exec_())