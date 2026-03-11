"""메인 윈도우 - 탭 컨테이너"""
from PyQt6.QtWidgets import QMainWindow, QTabWidget, QDockWidget, QPushButton, QLabel, QHBoxLayout, QWidget
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QSize, Qt
import sys
import os
from engine.models import DataManager
from ui.setup_tab import SetupTab
from ui.request_tab import RequestTab
from ui.rules_tab import RulesTab
from ui.result_tab import ResultTab
from ui.guide_panel import GuidePanel
from ui.styles import APP_STYLE


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

        # ── 가이드 사이드 패널 ──
        self.guide = GuidePanel()
        self._dock = QDockWidget(self)
        self._dock.setObjectName("guideDock")
        self._dock.setWidget(self.guide)
        self._dock.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea
            | Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self._dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        # 커스텀 타이틀바 (흰색 텍스트 보장)
        _title_bar = QWidget()
        _title_bar.setStyleSheet("background-color: #013976;")
        _title_layout = QHBoxLayout(_title_bar)
        _title_layout.setContentsMargins(10, 4, 10, 4)
        _title_label = QLabel("가이드")
        _title_label.setStyleSheet("color: white; font-weight: 600; font-family: '맑은 고딕'; font-size: 10pt;")
        _title_layout.addWidget(_title_label)
        _title_layout.addStretch()
        self._dock.setTitleBarWidget(_title_bar)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._dock)
        self._dock.setMinimumWidth(250)

        # 가이드 토글 버튼 (상태바)
        self._guide_btn = QPushButton("ⓘ 가이드")
        self._guide_btn.setObjectName("guideToggleBtn")
        self._guide_btn.setCheckable(True)
        self._guide_btn.setChecked(False)
        self._guide_btn.setFixedHeight(26)
        self._guide_btn.clicked.connect(self._toggle_guide)
        self._dock.visibilityChanged.connect(self._guide_btn.setChecked)
        self._dock.hide()
        self.statusBar().addPermanentWidget(self._guide_btn)

        # 상태바
        self.statusBar().showMessage("준비됨")

    def _toggle_guide(self, checked: bool):
        self._dock.setVisible(checked)

    def _on_tab_changed(self, index):
        self.guide.set_tab(index)

        if index == 1:  # 요청사항 탭
            nurses = self.setup_tab.get_nurses()
            start_date = self.setup_tab.get_start_date()
            rules = self.rules_tab.get_rules()
            self.request_tab.refresh(nurses, start_date, rules)
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
