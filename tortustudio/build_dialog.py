"""Build-executable dialog for TortuStudio.

Shows architecture checkboxes and streams PyInstaller / Podman output live.
The actual build runs on a QThread so the UI stays responsive.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from tortuengine.build_executable import (
    ARCH_ARM64,
    ARCH_ARMHF,
    ARCH_NATIVE,
    ARCH_X86_64,
    current_arch,
    podman_available,
    podman_networking_available,
    qemu_arm_available,
)


class _BuildWorker(QThread):
    log_line  = pyqtSignal(str)
    finished  = pyqtSignal(bool, str)

    def __init__(self, cart_root: Path, archs: list[str]) -> None:
        super().__init__()
        self.cart_root = cart_root
        self.archs     = archs

    def run(self) -> None:
        from tortuengine.build_executable import build_executable
        success = True
        for arch in self.archs:
            try:
                build_executable(self.cart_root, arch, log=self.log_line.emit)
            except Exception as exc:
                self.log_line.emit(f"[error] {exc}")
                success = False
        msg = "All builds finished." if success else "One or more builds failed."
        self.finished.emit(success, msg)


class BuildExecutableDialog(QDialog):
    def __init__(self, cart_root: Path, parent=None) -> None:
        super().__init__(parent)
        self.cart_root = cart_root
        self.setWindowTitle("Build Executable")
        self.setMinimumWidth(640)
        self._worker: _BuildWorker | None = None
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"Cart: {self.cart_root}"))

        # Architecture selection
        arch_group = QGroupBox("Target architectures")
        ag_layout  = QVBoxLayout(arch_group)

        native = current_arch()
        self._cb_native = QCheckBox(f"Current platform  ({native})")
        self._cb_native.setChecked(True)
        ag_layout.addWidget(self._cb_native)

        podman      = podman_available()
        networking  = podman and podman_networking_available()
        qemu        = podman and qemu_arm_available()
        cross_ready = networking and qemu

        def _cross_tooltip() -> str:
            if not podman:
                return "Install Podman to enable cross-compilation"
            parts = []
            if not networking:
                parts.append("network backend missing (sudo apt install passt)")
            if not qemu:
                parts.append(
                    "ARM emulation missing "
                    "(sudo apt install qemu-user-static && sudo systemctl restart systemd-binfmt)"
                )
            return " | ".join(parts)

        self._cb_arm64 = QCheckBox("ARM64  (via Podman — for Raspberry Pi 4 / Orange Pi)")
        if native == ARCH_ARM64:
            self._cb_arm64.setEnabled(False)
            self._cb_arm64.setToolTip("Already covered by current platform")
        elif not cross_ready:
            self._cb_arm64.setEnabled(False)
            self._cb_arm64.setToolTip(_cross_tooltip())
        ag_layout.addWidget(self._cb_arm64)

        self._cb_armhf = QCheckBox("ARMhf / ARM32  (via Podman — for older ARM boards)")
        if native == ARCH_ARMHF:
            self._cb_armhf.setEnabled(False)
            self._cb_armhf.setToolTip("Already covered by current platform")
        elif not cross_ready:
            self._cb_armhf.setEnabled(False)
            self._cb_armhf.setToolTip(_cross_tooltip())
        ag_layout.addWidget(self._cb_armhf)

        layout.addWidget(arch_group)

        hints: list[str] = []
        if not podman:
            hints.append("Podman not found — sudo apt install podman")
        else:
            if not networking:
                hints.append("Network backend missing — sudo apt install passt")
            if not qemu:
                hints.append(
                    "ARM emulation missing — sudo apt install qemu-user-static"
                    "  &&  sudo systemctl restart systemd-binfmt"
                )
        for text in hints:
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #cc8800;")
            layout.addWidget(lbl)

        # Log output
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Monospace", 9))
        self._log.setMinimumHeight(260)
        layout.addWidget(self._log)

        # Buttons
        self._btn_build = QPushButton("Build")
        self._btn_build.setDefault(True)
        self._btn_build.clicked.connect(self._start_build)

        self._btn_close = QPushButton("Close")
        self._btn_close.clicked.connect(self.reject)

        box = QDialogButtonBox()
        box.addButton(self._btn_build, QDialogButtonBox.ButtonRole.AcceptRole)
        box.addButton(self._btn_close, QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(box)

    def _selected_archs(self) -> list[str]:
        archs: list[str] = []
        if self._cb_native.isChecked():
            archs.append(ARCH_NATIVE)
        if self._cb_arm64.isChecked() and self._cb_arm64.isEnabled():
            archs.append(ARCH_ARM64)
        if self._cb_armhf.isChecked() and self._cb_armhf.isEnabled():
            archs.append(ARCH_ARMHF)
        return archs

    def _start_build(self) -> None:
        archs = self._selected_archs()
        if not archs:
            self._append("Select at least one architecture.")
            return

        self._btn_build.setEnabled(False)
        self._log.clear()
        self._append(f"Building for: {', '.join(archs)}")

        self._worker = _BuildWorker(self.cart_root, archs)
        self._worker.log_line.connect(self._append)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _append(self, line: str) -> None:
        self._log.appendPlainText(line)
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_finished(self, success: bool, msg: str) -> None:
        self._append(msg)
        self._btn_build.setEnabled(True)
        self._btn_close.setText("Done" if success else "Close")
