import sys
import winreg
import ctypes
import time
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QListWidget, QMessageBox, QComboBox, QSpinBox
)
from PySide6.QtCore import Qt

# --- 언어 텍스트 관리 ---
# 모든 UI 텍스트를 이곳에서 관리하여 다국어 지원을 용이하게 합니다.
LANGUAGES = {
    'en': {
        "window_title": "Chrome URLBlocklist Manager",
        "admin_error_title": "Administrator Privileges Required",
        "admin_error_message": "This program requires administrator privileges to modify the registry.\nPlease run as an administrator.",
        "os_error_title": "Compatibility Error",
        "os_error_message": "This program only runs on Windows.",
        "language_label": "Language:",
        "instructions_group": "How to Use",
        "instructions_text": "1. Enter the site you want to block (e.g., example.com).\n2. After adding, close all Chrome windows and restart it.\n(If not applied, please reboot your computer.)",
        "blocklist_group": "Manage Blocklist",
        "placeholder_text": "Enter domain...",
        "add_button": "Add",
        "remove_button": "Remove",
        "blocked_sites_label": "Blocked Sites:",
        "add_success_title": "Success",
        "add_success_message": "'{}' has been added.",
        "add_duplicate_title": "Duplicate",
        "add_duplicate_message": "'{}' already exists.",
        "remove_success_title": "Success",
        "remove_success_message": "'{}' has been removed.",
        "remove_fail_title": "Failed",
        "remove_fail_message": "'{}' could not be found.",
        "no_selection_title": "No Selection",
        "no_selection_message": "Please select a site from the list to remove.",
        "strict_lock_group": "Strict Lock",
        "strict_lock_label": "Lock for (hours):",
        "strict_lock_button": "Activate Lock",
        "lock_active_message": "Lock is active until: {}. The app will now close.",
        "focus_message_title": "Focus!",
        "focus_message_text": "Focus on your work! The settings are locked.",
        "status_ready": "Ready",
        "status_locked": "Locked until {}"
    },
    'ko': {
        "window_title": "Chrome URLBlocklist 관리자",
        "admin_error_title": "관리자 권한 필요",
        "admin_error_message": "이 프로그램은 레지스트리 수정을 위해 관리자 권한이 필요합니다.\n관리자 권한으로 실행해주세요.",
        "os_error_title": "호환성 오류",
        "os_error_message": "이 프로그램은 윈도우 환경에서만 동작합니다.",
        "language_label": "언어:",
        "instructions_group": "사용법",
        "instructions_text": "1. 차단하려는 사이트를 입력하세요 (예: example.com).\n2. 추가 후, 모든 크롬 창을 닫고 재시작하세요.\n(그래도 적용이 안 된다면 재부팅해주세요.)",
        "blocklist_group": "차단 목록 관리",
        "placeholder_text": "도메인 입력...",
        "add_button": "추가",
        "remove_button": "제거",
        "blocked_sites_label": "차단된 사이트 목록:",
        "add_success_title": "성공",
        "add_success_message": "'{}'가 추가되었습니다.",
        "add_duplicate_title": "중복",
        "add_duplicate_message": "'{}'는 이미 목록에 존재합니다.",
        "remove_success_title": "성공",
        "remove_success_message": "'{}'가 제거되었습니다.",
        "remove_fail_title": "실패",
        "remove_fail_message": "'{}'를 찾을 수 없습니다.",
        "no_selection_title": "선택 없음",
        "no_selection_message": "제거할 사이트를 목록에서 선택해주세요.",
        "strict_lock_group": "엄격 잠금",
        "strict_lock_label": "잠금 시간 (시간 단위):",
        "strict_lock_button": "잠금 활성화",
        "lock_active_message": "잠금이 {}까지 활성화되었습니다. 프로그램을 종료합니다.",
        "focus_message_title": "집중하세요!",
        "focus_message_text": "일에 집중하세요! 설정이 잠겨있습니다.",
        "status_ready": "준비됨",
        "status_locked": "{}까지 잠김"
    }
}


# --- 레지스트리 관리 클래스 ---
class RegistryManager:
    """레지스트리 관련 모든 작업을 처리하는 클래스"""
    POLICY_PATH = r"SOFTWARE\Policies\Google\Chrome\URLBlocklist"
    APP_SETTINGS_PATH = r"SOFTWARE\MyTools\ChromeBlocker"  # 앱 설정을 위한 별도 경로

    def _open_key(self, path, create=False):
        try:
            return winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_ALL_ACCESS)
        except FileNotFoundError:
            if create:
                return winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, path)
            return None

    def list_sites(self):
        key = self._open_key(self.POLICY_PATH)
        if not key:
            return []
        sites = []
        idx = 0
        while True:
            try:
                name, value, _ = winreg.EnumValue(key, idx)
                sites.append(value)
                idx += 1
            except OSError:
                break
        winreg.CloseKey(key)
        return sites

    def add_site(self, site):
        key = self._open_key(self.POLICY_PATH, create=True)
        sites = self.list_sites()
        if site.lower() in (s.lower() for s in sites):
            winreg.CloseKey(key)
            return False

        # 다음 인덱스 계산
        indices = []
        for i in range(len(sites) + 100):  # 여유롭게 탐색
            try:
                name, _, _ = winreg.EnumValue(key, i)
                if name.isdigit():
                    indices.append(int(name))
            except OSError:
                break
        next_idx = str(max(indices, default=0) + 1)

        winreg.SetValueEx(key, next_idx, 0, winreg.REG_SZ, site)
        winreg.CloseKey(key)
        return True

    def remove_site(self, site):
        key = self._open_key(self.POLICY_PATH)
        if not key:
            return False
        removed = False
        names_to_delete = []
        idx = 0
        while True:
            try:
                name, value, _ = winreg.EnumValue(key, idx)
                if value.lower() == site.lower():
                    names_to_delete.append(name)
                    removed = True
                idx += 1
            except OSError:
                break

        for name in names_to_delete:
            winreg.DeleteValue(key, name)

        winreg.CloseKey(key)
        return removed

    def set_lock_time(self, timestamp):
        key = self._open_key(self.APP_SETTINGS_PATH, create=True)
        winreg.SetValueEx(key, "LockUntil", 0, winreg.REG_SZ, str(timestamp))
        winreg.CloseKey(key)

    def get_lock_time(self):
        key = self._open_key(self.APP_SETTINGS_PATH)
        if not key:
            return 0.0
        try:
            value, _ = winreg.QueryValueEx(key, "LockUntil")
            return float(value)
        except FileNotFoundError:
            return 0.0
        finally:
            winreg.CloseKey(key)


# --- 메인 애플리케이션 클래스 ---
class BlocklistApp(QWidget):
    def __init__(self, registry_manager):
        super().__init__()
        self.registry = registry_manager
        self.current_lang = 'en'  # 기본 언어

        # 잠금 상태 확인
        self.check_lock_status_on_startup()

        self.init_ui()
        self.change_language('en')  # UI를 영어로 초기화
        self.refresh_list()

    def check_lock_status_on_startup(self):
        lock_until = self.registry.get_lock_time()
        if time.time() < lock_until:
            lang_texts = LANGUAGES[self.current_lang]
            QMessageBox.information(self, lang_texts["focus_message_title"], lang_texts["focus_message_text"])
            sys.exit(0)

    def init_ui(self):
        self.resize(500, 450)
        main_layout = QVBoxLayout(self)

        # 1. 언어 선택 섹션
        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel())  # 왼쪽 공간 채우기
        lang_layout.addStretch()
        self.lang_label = QLabel()
        lang_layout.addWidget(self.lang_label)
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["English", "한국어"])
        self.lang_combo.currentIndexChanged.connect(self.on_lang_change)
        lang_layout.addWidget(self.lang_combo)
        main_layout.addLayout(lang_layout)

        # 2. 사용법 섹션
        self.instructions_group = QGroupBox()
        instr_layout = QVBoxLayout()
        self.instructions_label = QLabel()
        self.instructions_label.setWordWrap(True)
        instr_layout.addWidget(self.instructions_label)
        self.instructions_group.setLayout(instr_layout)
        main_layout.addWidget(self.instructions_group)

        # 3. 차단 목록 관리 섹션
        self.blocklist_group = QGroupBox()
        blocklist_layout = QVBoxLayout()

        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.add_button = QPushButton()
        self.remove_button = QPushButton()
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.add_button)
        input_layout.addWidget(self.remove_button)
        blocklist_layout.addLayout(input_layout)

        self.blocked_sites_label = QLabel()
        blocklist_layout.addWidget(self.blocked_sites_label)
        self.list_widget = QListWidget()
        blocklist_layout.addWidget(self.list_widget)
        self.blocklist_group.setLayout(blocklist_layout)
        main_layout.addWidget(self.blocklist_group)

        # 4. 엄격 잠금 섹션
        self.strict_lock_group = QGroupBox()
        lock_layout = QHBoxLayout()
        self.strict_lock_label = QLabel()
        self.lock_hours_spinbox = QSpinBox()
        self.lock_hours_spinbox.setRange(1, 168)  # 1시간 ~ 1주일
        self.lock_hours_spinbox.setValue(1)
        self.lock_button = QPushButton()
        lock_layout.addWidget(self.strict_lock_label)
        lock_layout.addWidget(self.lock_hours_spinbox)
        lock_layout.addWidget(self.lock_button)
        self.strict_lock_group.setLayout(lock_layout)
        main_layout.addWidget(self.strict_lock_group)

        # 5. 상태바
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignRight)
        main_layout.addWidget(self.status_label)

        # 이벤트 연결
        self.add_button.clicked.connect(self.on_add)
        self.remove_button.clicked.connect(self.on_remove)
        self.lock_button.clicked.connect(self.on_lock)

    def on_lang_change(self, index):
        lang_code = 'en' if index == 0 else 'ko'
        self.change_language(lang_code)

    def change_language(self, lang_code):
        self.current_lang = lang_code
        texts = LANGUAGES[lang_code]

        self.setWindowTitle(texts["window_title"])
        self.lang_label.setText(texts["language_label"])
        self.instructions_group.setTitle(texts["instructions_group"])
        self.instructions_label.setText(texts["instructions_text"])
        self.blocklist_group.setTitle(texts["blocklist_group"])
        self.input_field.setPlaceholderText(texts["placeholder_text"])
        self.add_button.setText(texts["add_button"])
        self.remove_button.setText(texts["remove_button"])
        self.blocked_sites_label.setText(texts["blocked_sites_label"])
        self.strict_lock_group.setTitle(texts["strict_lock_group"])
        self.strict_lock_label.setText(texts["strict_lock_label"])
        self.lock_button.setText(texts["strict_lock_button"])
        self.status_label.setText(texts["status_ready"])

    def refresh_list(self):
        self.list_widget.clear()
        try:
            sites = self.registry.list_sites()
            for site in sorted(sites):
                self.list_widget.addItem(site)
        except Exception as e:
            # 오류 발생 시 사용자에게 알림 (예: 권한 문제)
            # 이 부분은 is_admin() 체크로 대부분 예방됩니다.
            print(f"Error refreshing list: {e}")

    def on_add(self):
        site = self.input_field.text().strip()
        if not site:
            return

        texts = LANGUAGES[self.current_lang]
        if self.registry.add_site(site):
            QMessageBox.information(self, texts["add_success_title"], texts["add_success_message"].format(site))
            self.input_field.clear()
        else:
            QMessageBox.warning(self, texts["add_duplicate_title"], texts["add_duplicate_message"].format(site))
        self.refresh_list()

    def on_remove(self):
        selected_item = self.list_widget.currentItem()
        texts = LANGUAGES[self.current_lang]
        if not selected_item:
            QMessageBox.warning(self, texts["no_selection_title"], texts["no_selection_message"])
            return

        site = selected_item.text()
        if self.registry.remove_site(site):
            QMessageBox.information(self, texts["remove_success_title"], texts["remove_success_message"].format(site))
        else:
            QMessageBox.warning(self, texts["remove_fail_title"], texts["remove_fail_message"].format(site))
        self.refresh_list()

    def on_lock(self):
        texts = LANGUAGES[self.current_lang]
        hours = self.lock_hours_spinbox.value()
        lock_until_timestamp = time.time() + hours * 3600

        self.registry.set_lock_time(lock_until_timestamp)

        lock_end_time_str = datetime.fromtimestamp(lock_until_timestamp).strftime('%Y-%m-%d %H:%M:%S')
        QMessageBox.information(self, texts["strict_lock_group"],
                                texts["lock_active_message"].format(lock_end_time_str))

        self.close()


# --- 프로그램 진입점 ---
def is_admin():
    """관리자 권한으로 실행되었는지 확인"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 윈도우 환경인지 확인
    if not sys.platform.startswith("win"):
        QMessageBox.critical(None, LANGUAGES['en']["os_error_title"], LANGUAGES['en']["os_error_message"])
        sys.exit(1)

    # 관리자 권한인지 확인
    if not is_admin():
        # 기본 언어인 영어로 메시지 표시
        QMessageBox.critical(None, LANGUAGES['en']["admin_error_title"], LANGUAGES['en']["admin_error_message"])
        sys.exit(1)

    registry = RegistryManager()
    window = BlocklistApp(registry)
    window.show()

    sys.exit(app.exec())
