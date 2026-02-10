"""메인 윈도우 - 탭 컨테이너"""
from PyQt6.QtWidgets import QMainWindow, QTabWidget, QStatusBar
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtCore import Qt
from engine.models import DataManager
from ui.setup_tab import SetupTab
from ui.request_tab import RequestTab
from ui.rules_tab import RulesTab
from ui.result_tab import ResultTab
from ui.styles import APP_STYLE, FONT_FAMILY


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.dm = DataManager()
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("NurseScheduler - 간호사 근무표 자동생성")
        self.setMinimumSize(1200, 700)
        self.resize(1400, 800)
        self.setStyleSheet(APP_STYLE)

        # 탭 위젯
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Tab 1: 설정
        self.setup_tab = SetupTab(self.dm)
        self.tabs.addTab(self.setup_tab, "📋 설정")

        # Tab 2: 요청사항
        self.request_tab = RequestTab(self.dm)
        self.tabs.addTab(self.request_tab, "📅 요청사항")

        # Tab 3: 규칙
        self.rules_tab = RulesTab(self.dm)
        self.tabs.addTab(self.rules_tab, "⚙️ 규칙설정")

        # Tab 4: 결과
        self.result_tab = ResultTab(self.dm)
        self.tabs.addTab(self.result_tab, "📊 결과")

        # 탭 전환 시 데이터 동기화
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # 상태바
        self.statusBar().showMessage("준비됨")

    def _on_tab_changed(self, index):
        if index == 1:  # 요청사항 탭
            nurses = self.setup_tab.get_nurses()
            year, month = self.setup_tab.get_year_month()
            self.request_tab.refresh(nurses, year, month)
            self.statusBar().showMessage(f"{year}년 {month}월 요청사항 편집 중")

        elif index == 2:  # 규칙 탭
            year, month = self.setup_tab.get_year_month()
            self.rules_tab.set_year_month(year, month)

        elif index == 3:  # 결과 탭
            nurses = self.setup_tab.get_nurses()
            requests = self.request_tab.get_requests()
            rules = self.rules_tab.get_rules()
            year, month = self.setup_tab.get_year_month()
            self.result_tab.set_schedule_data(nurses, requests, rules, year, month)
            self.statusBar().showMessage(f"{year}년 {month}월 | 간호사 {len(nurses)}명 | '근무표 생성' 클릭")
