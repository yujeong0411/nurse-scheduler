"""메인 윈도우 - 탭 컨테이너"""
from PyQt6.QtWidgets import QMainWindow, QTabWidget
from PyQt6.QtGui import QIcon, QAction, QKeySequence
from PyQt6.QtCore import QSize, QTimer
import sys
import os
from engine.models import DataManager
from ui.setup_tab import SetupTab
from ui.request_tab import RequestTab
from ui.rules_tab import RulesTab
from ui.result_tab import ResultTab
from ui.styles import APP_STYLE


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.dm = DataManager()
        self._init_ui()
        # 첫 실행 체크 (UI가 완전히 표시된 후 실행)
        QTimer.singleShot(300, self._check_first_launch)

    def _init_ui(self):
        self.setWindowTitle("NurseScheduler - 간호사 근무표 자동생성")
        self.setMinimumSize(1200, 700)
        self.resize(1400, 800)
        self.setStyleSheet(APP_STYLE)

        # --- 메뉴바 ---
        self._init_menubar()

        # 탭 위젯
        self.tabs = QTabWidget()
        self.tabs.setIconSize(QSize(20, 20))
        self.setCentralWidget(self.tabs)

        # --- 아이콘 경로 설정 ---
        def get_icon(name):
            # 1. 현재 MainWindow.py의 위치 (./ui/)
            current_dir = os.path.dirname(os.path.abspath(__file__))

            # 2. 부모 폴더(최상단 루트)로 한 단계 이동 (../)
            project_root = os.path.dirname(current_dir)

            # 3. 루트에 있는 assets/icons 폴더 내의 파일 경로 생성
            icon_path = os.path.join(project_root, "assets", "icons", name)

            return QIcon(icon_path)

        # Tab 1: 설정
        self.setup_tab = SetupTab(self.dm)
        self.tabs.addTab(self.setup_tab, get_icon("settings.svg"), "설정")

        # Tab 2: 요청사항
        self.request_tab = RequestTab(self.dm)
        self.tabs.addTab(self.request_tab, get_icon("requests.svg"), "요청사항")

        # Tab 3: 규칙
        self.rules_tab = RulesTab(self.dm)
        self.tabs.addTab(self.rules_tab, get_icon("rule_settings.svg"), "규칙설정")

        # Tab 4: 결과
        self.result_tab = ResultTab(self.dm)
        self.tabs.addTab(self.result_tab, get_icon("result.svg"), "결과")

        # 탭 전환 시 데이터 동기화
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # 상태바
        self.statusBar().showMessage("준비됨")

    def _init_menubar(self):
        """메뉴바 생성"""
        menubar = self.menuBar()

        # 도움말 메뉴
        help_menu = menubar.addMenu("도움말")

        # 사용 가이드 (F1)
        action_guide = QAction("사용 가이드", self)
        action_guide.setShortcut(QKeySequence("F1"))
        action_guide.triggered.connect(lambda: self._show_help(welcome=False))
        help_menu.addAction(action_guide)

        # 처음 사용자 가이드
        action_welcome = QAction("처음 사용자 가이드", self)
        action_welcome.triggered.connect(lambda: self._show_help(welcome=True))
        help_menu.addAction(action_welcome)

    def _show_help(self, welcome=False):
        """도움말 다이얼로그 표시"""
        from ui.help_dialog import HelpDialog
        dlg = HelpDialog(self, welcome=welcome)
        dlg.exec()
        if welcome and dlg.should_hide_welcome():
            settings = self.dm.load_settings()
            settings["show_welcome"] = False
            self.dm.save_settings(settings)

    def _check_first_launch(self):
        """첫 실행 시 환영 다이얼로그 표시"""
        settings = self.dm.load_settings()
        if settings.get("show_welcome", True):
            self._show_help(welcome=True)

    def _on_tab_changed(self, index):
        if index == 1:  # 요청사항 탭
            nurses = self.setup_tab.get_nurses()
            start_date = self.setup_tab.get_start_date()
            self.request_tab.refresh(nurses, start_date)
            self.statusBar().showMessage(f"{start_date.isoformat()} 요청사항 편집 중")

        elif index == 2:  # 규칙 탭
            start_date = self.setup_tab.get_start_date()
            self.rules_tab.set_start_date(start_date)

        elif index == 3:  # 결과 탭
            nurses = self.setup_tab.get_nurses()
            requests = self.request_tab.get_requests()
            rules = self.rules_tab.get_rules()
            start_date = self.setup_tab.get_start_date()
            self.result_tab.set_schedule_data(nurses, requests, rules, start_date)
            self.statusBar().showMessage(f"{start_date.isoformat()} | 간호사 {len(nurses)}명 | '근무표 생성' 클릭")
