'''*************************************************
content     Optical - OCR

version     0.0.1
date        21-04-2026

author      Harry Shaper <harryshaper@gmail.com>

*************************************************'''

import os
import re
import sys
import importlib
from pathlib import Path
from Qt import QtWidgets, QtGui, QtCore, QtCompat

# CONSTANTS
TITLE = Path(__file__).stem
CURRENT_PATH = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_PATH.parent

ICONS_DIR = ROOT_DIR / "assets" / "Icons"
UI_PATH = CURRENT_PATH / "ui" / "Optical_20260430.ui"


def icon_path(name):
	return str(ICONS_DIR / f"{name}.png")


# ******************************************************************************
# HELPERS

class PreviewEventFilter(QtCore.QObject):
	def __init__(self, optical_instance):
		super().__init__()
		self.optical = optical_instance

	def eventFilter(self, obj, event):
		if obj is self.optical.wgOptical.imageView.viewport():
			if event.type() == QtCore.QEvent.Wheel:
				return self.optical.handle_preview_wheel(event)

			if event.type() == QtCore.QEvent.MouseButtonDblClick:
				self.optical.reset_preview_zoom()
				return True

		return super().eventFilter(obj, event)


class StageResizeFilter(QtCore.QObject):
	def __init__(self, optical_instance):
		super().__init__()
		self.optical = optical_instance

	def eventFilter(self, obj, event):
		if obj is self.optical.wgOptical.previewStage:
			if event.type() == QtCore.QEvent.Resize:
				self.optical.resize_preview()

		return super().eventFilter(obj, event)


class FolderItemWidget(QtWidgets.QWidget):
	def __init__(self, original_name, suggested_name="", status="pending"):
		super().__init__()

		self.setSizePolicy(
			QtWidgets.QSizePolicy.Expanding,
			QtWidgets.QSizePolicy.Fixed
		)
		self.setMinimumHeight(56)

		self.name_label = QtWidgets.QLabel(original_name)
		self.name_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

		self.suggested_label = QtWidgets.QLabel(suggested_name)
		self.suggested_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

		self.status_indicator = QtWidgets.QLabel()
		self.status_indicator.setFixedSize(12, 12)

		text_layout = QtWidgets.QVBoxLayout()
		text_layout.setContentsMargins(0, 0, 0, 0)
		text_layout.setSpacing(2)
		text_layout.addWidget(self.name_label)
		text_layout.addWidget(self.suggested_label)

		main_layout = QtWidgets.QHBoxLayout(self)
		main_layout.setContentsMargins(12, 6, 12, 8)
		main_layout.setSpacing(8)
		main_layout.addLayout(text_layout)
		main_layout.addStretch()
		main_layout.addWidget(self.status_indicator, 0, QtCore.Qt.AlignVCenter)

		self._status = status
		self._selected = False

		self.set_suggested_name(suggested_name)
		self.set_status(status)
		self.set_selected(False)

	def set_suggested_name(self, suggested_name):
		suggested_name = (suggested_name or "").strip()

		if suggested_name:
			self.suggested_label.setText(suggested_name)
		else:
			self.suggested_label.setText("No suggestion")

		self._apply_styles()

	def set_status(self, status):
		self._status = status

		color_map = {
			"confirmed": "#4CAF50",
			"pending": "#FF9800",
			"ignored": "#F44336",
		}
		color = color_map.get(status, "#777777")

		self.status_indicator.setStyleSheet(f"""
			background-color: {color};
			border-radius: 6px;
		""")

		self.setToolTip(status.capitalize())
		self._apply_styles()

	def set_selected(self, selected):
		self._selected = selected
		self._apply_styles()

	def _apply_styles(self):
		if self._selected:
			self.setStyleSheet("""
				FolderItemWidget, QWidget {
					background-color: #3a320f;
				}
			""")
			name_color = "#f0b000"
			suggested_color = "#d8c27a"
		else:
			self.setStyleSheet("""
				FolderItemWidget, QWidget {
					background-color: transparent;
				}
			""")
			if self._status == "ignored":
				name_color = "#9a9a9a"
			else:
				name_color = "#ededed"

			if self.suggested_label.text().strip().upper() == "NO SUGGESTION":
				suggested_color = "#7f7f7f"
			else:
				suggested_color = "#bfbfbf"

		self.name_label.setStyleSheet(
			f"color: {name_color}; font-size: 12px; font-weight: 600; background: transparent;"
		)
		self.suggested_label.setStyleSheet(
			f"color: {suggested_color}; font-size: 11px; background: transparent;"
		)

	def sizeHint(self):
		return QtCore.QSize(240, 56)

class ThumbnailItemWidget(QtWidgets.QFrame):
	def __init__(self, pixmap=None, selected=False, parent=None):
		super().__init__(parent)

		self.setObjectName("thumbnailItemWidget")
		self.setFixedSize(112, 68)

		self.thumb_holder = QtWidgets.QWidget()
		self.thumb_holder.setFixedSize(96, 44)
		self.thumb_holder.setStyleSheet("background: transparent; border: none;")

		self.image_label = QtWidgets.QLabel(self.thumb_holder)
		self.image_label.setAlignment(QtCore.Qt.AlignCenter)
		self.image_label.setGeometry(0, 0, 96, 44)
		self.image_label.setStyleSheet("background: transparent; border: none;")

		main_layout = QtWidgets.QVBoxLayout(self)
		main_layout.setContentsMargins(8, 12, 8, 12)
		main_layout.setSpacing(0)
		main_layout.addWidget(self.thumb_holder, 0, QtCore.Qt.AlignCenter)

		self.set_pixmap(pixmap)
		self.set_selected(selected)

	def set_pixmap(self, pixmap):
		self.image_label.clear()

		if pixmap is None or pixmap.isNull():
			return

		scaled = pixmap.scaled(
			96,
			44,
			QtCore.Qt.KeepAspectRatio,
			QtCore.Qt.SmoothTransformation
		)

		canvas = QtGui.QPixmap(96, 44)
		canvas.fill(QtCore.Qt.transparent)

		painter = QtGui.QPainter(canvas)
		x = (96 - scaled.width()) // 2
		y = (44 - scaled.height()) // 2 - 2
		y = max(0, min(y, 44 - scaled.height()))
		painter.drawPixmap(x, y, scaled)
		painter.end()

		self.image_label.setPixmap(canvas)

	def set_selected(self, selected):
		if selected:
			self.setStyleSheet("""
				QFrame#thumbnailItemWidget {
					background-color: #343434;
					border: 1px solid #5c5c5c;
				}
			""")
		else:
			self.setStyleSheet("""
				QFrame#thumbnailItemWidget {
					background-color: transparent;
					border: 1px solid transparent;
				}
			""")

class OCRProgressDialog(QtWidgets.QDialog):
	def __init__(self, title="Auto-Run OCR", heading="Initializing OCR...", detail="", parent=None):
		super().__init__(parent)

		self.setWindowTitle(title)
		self.setWindowIcon(QtGui.QIcon(icon_path("logo")))
		self.setModal(True)
		self.setFixedSize(460, 185)

		self._was_canceled = False

		self.setStyleSheet("""
			QDialog {
				background-color: #2f2f2f;
			}

			QLabel {
				background-color: transparent;
			}

			QLabel#headingLabel {
				color: #d8a106;
				font-size: 16px;
				font-weight: 600;
			}

			QLabel#detailLabel {
				color: #f2f2f2;
				font-size: 13px;
				font-weight: 400;
			}

			QLabel#subDetailLabel {
				color: #bfbfbf;
				font-size: 11px;
				font-weight: 400;
			}

			QProgressBar {
				background-color: #1f1f1f;
				border: 1px solid #4a4a4a;
				border-radius: 2px;
				height: 20px;
				text-align: center;
				color: #ededed;
				font-size: 11px;
			}

			QProgressBar::chunk {
				background-color: #2E7D32;
			}

			QPushButton {
				background-color: #c99700;
				color: black;
				border: none;
				padding: 5px 14px;
				min-width: 72px;
				min-height: 30px;
				font-size: 12px;
				font-weight: 500;
			}

			QPushButton:hover {
				background-color: #d8a106;
			}

			QPushButton:pressed {
				background-color: #b88705;
			}

			QPushButton#btn_cancel {
				background-color: #C62828;
				color: #ededed;
			}

			QPushButton#btn_cancel:hover {
				background-color: #D32F2F;
			}

			QPushButton#btn_cancel:pressed {
				background-color: #8E1C1C;
			}
		""")

		main_layout = QtWidgets.QVBoxLayout(self)
		main_layout.setContentsMargins(24, 18, 24, 18)
		main_layout.setSpacing(10)

		self.heading_label = QtWidgets.QLabel(heading)
		self.heading_label.setObjectName("headingLabel")
		self.heading_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
		main_layout.addWidget(self.heading_label)

		self.detail_label = QtWidgets.QLabel(detail)
		self.detail_label.setObjectName("detailLabel")
		self.detail_label.setWordWrap(True)
		self.detail_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
		main_layout.addWidget(self.detail_label)

		self.sub_detail_label = QtWidgets.QLabel("")
		self.sub_detail_label.setObjectName("subDetailLabel")
		self.sub_detail_label.setWordWrap(True)
		self.sub_detail_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
		main_layout.addWidget(self.sub_detail_label)

		self.progress_bar = QtWidgets.QProgressBar()
		self.progress_bar.setRange(0, 100)
		self.progress_bar.setValue(0)
		main_layout.addWidget(self.progress_bar)

		main_layout.addStretch()

		button_layout = QtWidgets.QHBoxLayout()
		button_layout.addStretch()

		self.cancel_button = QtWidgets.QPushButton("Cancel")
		self.cancel_button.setObjectName("btn_cancel")
		self.cancel_button.clicked.connect(self.cancel)
		button_layout.addWidget(self.cancel_button)

		main_layout.addLayout(button_layout)

	def set_heading(self, text):
		self.heading_label.setText(text)

	def set_detail(self, text):
		self.detail_label.setText(text)

	def set_sub_detail(self, text):
		self.sub_detail_label.setText(text)

	def set_progress(self, value, maximum):
		maximum = max(1, maximum)
		self.progress_bar.setRange(0, maximum)
		self.progress_bar.setValue(value)

	def cancel(self):
		self._was_canceled = True
		self.reject()

	def was_canceled(self):
		return self._was_canceled

class CustomMessageDialog(QtWidgets.QDialog):
	def __init__(self, title, heading, detail="", sub_detail="", parent=None):
		super().__init__(parent)

		self.setWindowTitle(title)
		self.setWindowIcon(QtGui.QIcon(icon_path("logo")))
		self.setModal(True)
		self.setFixedSize(430, 165)

		self.setStyleSheet("""
			QDialog {
				background-color: #2f2f2f;
			}

			QLabel {
				background-color: transparent;
			}

			QLabel#headingLabel {
				color: #d8a106;
				font-size: 16px;
				font-weight: 600;
			}

			QLabel#detailLabel {
				color: #f2f2f2;
				font-size: 13px;
				font-weight: 400;
			}

			QLabel#subDetailLabel {
				color: #bfbfbf;
				font-size: 11px;
				font-weight: 400;
			}

			QPushButton {
				background-color: #c99700;
				color: black;
				border: none;
				padding: 5px 14px;
				min-width: 72px;
				min-height: 30px;
				font-size: 12px;
				font-weight: 500;
			}

			QPushButton:hover {
				background-color: #d8a106;
			}

			QPushButton:pressed {
				background-color: #b88705;
			}
		""")

		main_layout = QtWidgets.QVBoxLayout(self)
		main_layout.setContentsMargins(24, 18, 24, 18)
		main_layout.setSpacing(8)

		self.heading_label = QtWidgets.QLabel(heading)
		self.heading_label.setObjectName("headingLabel")
		self.heading_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
		main_layout.addWidget(self.heading_label)

		if detail:
			self.detail_label = QtWidgets.QLabel(detail)
			self.detail_label.setObjectName("detailLabel")
			self.detail_label.setWordWrap(False)
			self.detail_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
			main_layout.addWidget(self.detail_label)

		if sub_detail:
			self.sub_detail_label = QtWidgets.QLabel(sub_detail)
			self.sub_detail_label.setObjectName("subDetailLabel")
			self.sub_detail_label.setWordWrap(True)
			self.sub_detail_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
			main_layout.addWidget(self.sub_detail_label)

		main_layout.addStretch()

		button_layout = QtWidgets.QHBoxLayout()
		button_layout.addStretch()

		self.ok_button = QtWidgets.QPushButton("OK")
		self.ok_button.clicked.connect(self.accept)
		button_layout.addWidget(self.ok_button)

		main_layout.addLayout(button_layout)

class ConfirmActionDialog(QtWidgets.QDialog):
	def __init__(self, title, heading, detail="", sub_detail="", confirm_text="Continue", parent=None):
		super().__init__(parent)

		self.setWindowTitle(title)
		self.setWindowIcon(QtGui.QIcon(icon_path("logo")))
		self.setModal(True)
		self.setFixedSize(430, 175)

		self.setStyleSheet("""
			QDialog {
				background-color: #2f2f2f;
			}

			QLabel {
				background-color: transparent;
			}

			QLabel#headingLabel {
				color: #d8a106;
				font-size: 16px;
				font-weight: 600;
			}

			QLabel#detailLabel {
				color: #f2f2f2;
				font-size: 13px;
				font-weight: 400;
			}

			QLabel#subDetailLabel {
				color: #bfbfbf;
				font-size: 11px;
				font-weight: 400;
			}

			QPushButton {
				background-color: #c99700;
				color: black;
				border: none;
				padding: 5px 14px;
				min-width: 72px;
				min-height: 30px;
				font-size: 12px;
				font-weight: 500;
			}

			QPushButton:hover {
				background-color: #d8a106;
			}

			QPushButton:pressed {
				background-color: #b88705;
			}

			QPushButton#btn_cancel {
				background-color: #4a4a4a;
				color: #ededed;
			}

			QPushButton#btn_cancel:hover {
				background-color: #5a5a5a;
			}

			QPushButton#btn_cancel:pressed {
				background-color: #3a3a3a;
			}
		""")

		main_layout = QtWidgets.QVBoxLayout(self)
		main_layout.setContentsMargins(24, 18, 24, 18)
		main_layout.setSpacing(8)

		self.heading_label = QtWidgets.QLabel(heading)
		self.heading_label.setObjectName("headingLabel")
		self.heading_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
		main_layout.addWidget(self.heading_label)

		if detail:
			self.detail_label = QtWidgets.QLabel(detail)
			self.detail_label.setObjectName("detailLabel")
			self.detail_label.setWordWrap(True)
			self.detail_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
			main_layout.addWidget(self.detail_label)

		if sub_detail:
			self.sub_detail_label = QtWidgets.QLabel(sub_detail)
			self.sub_detail_label.setObjectName("subDetailLabel")
			self.sub_detail_label.setWordWrap(True)
			self.sub_detail_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
			main_layout.addWidget(self.sub_detail_label)

		main_layout.addStretch()

		button_layout = QtWidgets.QHBoxLayout()
		button_layout.addStretch()

		self.cancel_button = QtWidgets.QPushButton("Cancel")
		self.cancel_button.setObjectName("btn_cancel")
		self.cancel_button.clicked.connect(self.reject)
		button_layout.addWidget(self.cancel_button)

		self.confirm_button = QtWidgets.QPushButton(confirm_text)
		self.confirm_button.clicked.connect(self.accept)
		button_layout.addWidget(self.confirm_button)

		main_layout.addLayout(button_layout)

# ******************************************************************************
# CLASSES

class Optical:

	def __init__(self):
		self.wgOptical = QtCompat.loadUi(str(UI_PATH))

		# ----------------------------------------------------------------------
		# STATE
		self.current_target_folder = ""
		self.current_folder_path = ""
		self.current_folder_images = []
		self.current_image_index = 0
		self.preview_zoom = 0
		self.is_resizing_preview = False
		self.folder_name_edits = {}
		self.folder_ocr_suggestions = {}
		self.folder_records = {}
		self._ocr_module = None

		# OCR SETTINGS
		self.ocr_settings = {
			"mode": "last_n",          # "first", "last", "first_n", "last_n", "all"
			"padding": 3,              # used for *_n modes
			"stop_on_first_hit": True
		}

		# ----------------------------------------------------------------------
		# OVERLAY LABEL SETUP
		if hasattr(self.wgOptical, "label_originalFolderName"):
			self.wgOptical.label_originalFolderName.setWordWrap(False)
			self.wgOptical.label_originalFolderName.setSizePolicy(
				QtWidgets.QSizePolicy.Fixed,
				QtWidgets.QSizePolicy.Fixed
			)
			self.wgOptical.label_originalFolderName.hide()

		self.overlay_resize_timer = QtCore.QTimer(self.wgOptical)
		self.overlay_resize_timer.setSingleShot(True)
		self.overlay_resize_timer.timeout.connect(self.finish_preview_resize)

		# ----------------------------------------------------------------------
		# PREVIEW VIEWER SETUP
		self.preview_scene = QtWidgets.QGraphicsScene(self.wgOptical.imageView)
		self.preview_pixmap_item = QtWidgets.QGraphicsPixmapItem()
		self.preview_scene.addItem(self.preview_pixmap_item)
		self.preview_scene.setBackgroundBrush(QtGui.QBrush(QtGui.QColor("#3a3a3a")))

		self.wgOptical.imageView.setScene(self.preview_scene)
		self.wgOptical.imageView.setRenderHints(
			QtGui.QPainter.Antialiasing |
			QtGui.QPainter.SmoothPixmapTransform
		)
		self.wgOptical.imageView.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
		self.wgOptical.imageView.setResizeAnchor(QtWidgets.QGraphicsView.AnchorViewCenter)
		self.wgOptical.imageView.setAlignment(QtCore.Qt.AlignCenter)
		self.wgOptical.imageView.setDragMode(QtWidgets.QGraphicsView.NoDrag)
		self.wgOptical.imageView.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
		self.wgOptical.imageView.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
		self.wgOptical.imageView.setFrameShape(QtWidgets.QFrame.NoFrame)
		self.wgOptical.imageView.setSizePolicy(
			QtWidgets.QSizePolicy.Expanding,
			QtWidgets.QSizePolicy.Expanding
		)
		self.wgOptical.imageView.setMinimumSize(0, 0)
		self.wgOptical.imageView.setMaximumSize(16777215, 16777215)

		self.thumbnail_icon_cache = {}

		# VIEWER UPDATE / PERFORMANCE
		self.wgOptical.imageView.setViewportUpdateMode(
			QtWidgets.QGraphicsView.SmartViewportUpdate
		)
		self.wgOptical.imageView.setOptimizationFlag(
			QtWidgets.QGraphicsView.DontAdjustForAntialiasing, True
		)
		self.wgOptical.imageView.setCacheMode(
			QtWidgets.QGraphicsView.CacheBackground
		)

		self.preview_pixmap_cache = {}
		self.preview_pixmap_cache_limit = 12

		self.wgOptical.thumbnailStrip = QtWidgets.QListWidget()
		self.wgOptical.thumbnailStrip.setObjectName("thumbnailStrip")
		self.wgOptical.thumbnailStrip.setViewMode(QtWidgets.QListView.IconMode)
		self.wgOptical.thumbnailStrip.setFlow(QtWidgets.QListView.LeftToRight)
		self.wgOptical.thumbnailStrip.setResizeMode(QtWidgets.QListView.Adjust)
		self.wgOptical.thumbnailStrip.setMovement(QtWidgets.QListView.Static)
		self.wgOptical.thumbnailStrip.setWrapping(False)
		self.wgOptical.thumbnailStrip.setUniformItemSizes(True)
		self.wgOptical.thumbnailStrip.setSelectionRectVisible(False)
		self.wgOptical.thumbnailStrip.setSpacing(6)
		self.wgOptical.thumbnailStrip.setFixedHeight(92)
		self.wgOptical.thumbnailStrip.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
		self.wgOptical.thumbnailStrip.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
		self.wgOptical.thumbnailStrip.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
		self.wgOptical.thumbnailStrip.setFrameShape(QtWidgets.QFrame.NoFrame)
		self.wgOptical.thumbnailStrip.setStyleSheet("""
			QListWidget#thumbnailStrip {
				background-color: #141414;
				border: none;
				padding: 2px 4px 2px 4px;
				outline: none;
			}
		""")
		self.wgOptical.thumbnailStrip.itemClicked.connect(self.on_thumbnail_clicked)

		preview_layout = self.wgOptical.page_previewImage.layout()
		if preview_layout is not None:
			self._insert_thumbnail_strip_recursive(preview_layout)

		# ----------------------------------------------------------------------
		# PREVIEW PAGE THEMING	
		self.wgOptical.page_previewImage.setStyleSheet("""
			QWidget#page_previewImage {
				background-color: #2b2b2b;
			}
		""")

		self.wgOptical.previewStage.setStyleSheet("""
			QWidget#previewStage {
				background-color: #313131;
				border: none;
			}
		""")

		self.wgOptical.row_textEdit.setStyleSheet("""
			QWidget#row_textEdit {
				background-color: #090909;
				border-top: 1px solid #2a2a2a;
			}
		""")

		self.wgOptical.horizontalLayout_10.setSpacing(12)
		self.wgOptical.horizontalLayout_10.setContentsMargins(16, 10, 16, 10)
		# ----------------------------------------------------------------------
		# EVENT FILTERS
		self.preview_event_filter = PreviewEventFilter(self)
		self.wgOptical.imageView.viewport().installEventFilter(self.preview_event_filter)

		self.stage_resize_filter = StageResizeFilter(self)
		if hasattr(self.wgOptical, "previewStage"):
			self.wgOptical.previewStage.installEventFilter(self.stage_resize_filter)

		if hasattr(self.wgOptical, "label_originalFolderName") and hasattr(self.wgOptical, "previewCanvas"):
			self.wgOptical.label_originalFolderName.setParent(self.wgOptical.previewCanvas)
			self.wgOptical.label_originalFolderName.hide()

		# Create preview status dot in code so it always exists
		if hasattr(self.wgOptical, "previewCanvas"):
			self.wgOptical.label_statusDot = QtWidgets.QLabel(self.wgOptical.previewCanvas)
			self.wgOptical.label_statusDot.setObjectName("label_statusDot")
			self.wgOptical.label_statusDot.setFixedSize(16, 16)
			self.wgOptical.label_statusDot.hide()

		# KEYBOARD SHORTCUTS
		self.shortcut_confirm = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Return), self.wgOptical)
		self.shortcut_confirm.setContext(QtCore.Qt.ApplicationShortcut)
		self.shortcut_confirm.activated.connect(self.press_confirm)

		self.shortcut_confirm_enter = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Enter), self.wgOptical)
		self.shortcut_confirm_enter.setContext(QtCore.Qt.ApplicationShortcut)
		self.shortcut_confirm_enter.activated.connect(self.press_confirm)

		self.shortcut_ignore = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Delete), self.wgOptical)
		self.shortcut_ignore.setContext(QtCore.Qt.ApplicationShortcut)
		self.shortcut_ignore.activated.connect(self.press_ignore)

		self.shortcut_folder_up = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Up), self.wgOptical)
		self.shortcut_folder_up.setContext(QtCore.Qt.ApplicationShortcut)
		self.shortcut_folder_up.activated.connect(self.select_previous_folder)

		self.shortcut_folder_down = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Down), self.wgOptical)
		self.shortcut_folder_down.setContext(QtCore.Qt.ApplicationShortcut)
		self.shortcut_folder_down.activated.connect(self.select_next_folder)

		self.shortcut_image_left = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Left), self.wgOptical)
		self.shortcut_image_left.setContext(QtCore.Qt.ApplicationShortcut)
		self.shortcut_image_left.activated.connect(self.show_previous_image)

		self.shortcut_image_right = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Right), self.wgOptical)
		self.shortcut_image_right.setContext(QtCore.Qt.ApplicationShortcut)
		self.shortcut_image_right.activated.connect(self.show_next_image)

		# ----------------------------------------------------------------------
		# TOOL ICONS
		self.wgOptical.btn_browseTargetFolder.setIcon(
			QtGui.QIcon(icon_path("browse_file_icon"))
		)

		self.wgOptical.input_targetFolder.setFixedHeight(24)
		self.wgOptical.btn_browseTargetFolder.setFixedSize(24, 24)

		self.wgOptical.input_targetFolder.setContentsMargins(0, 0, 0, 0)
		self.wgOptical.btn_browseTargetFolder.setContentsMargins(0, 0, 0, 0)

		self.wgOptical.btn_browseTargetFolder.setStyleSheet("""
		QPushButton {
			background-color: #f0b000;
			border: none;
			padding: 0px;
			margin: 0px;
		}
		QPushButton:hover {
			background-color: #ffc533;
		}
		QPushButton:pressed {
			background-color: #d89c00;
		}
		""")

		# ----------------------------------------------------------------------
		# SIGNALS
		self.wgOptical.btn_browseTargetFolder.clicked.connect(self.press_browseTargetFolder)
		self.wgOptical.input_targetFolder.textChanged.connect(self.update_target_folder_state)
		self.wgOptical.list_folders.currentRowChanged.connect(self.on_folder_selected)
		self.wgOptical.lineEdit_textInput.textChanged.connect(self.on_text_input_changed)

		if hasattr(self.wgOptical, "btn_confirm"):
			self.wgOptical.btn_confirm.clicked.connect(self.press_confirm)

		if hasattr(self.wgOptical, "btn_ignore"):
			self.wgOptical.btn_ignore.clicked.connect(self.press_ignore)

		if hasattr(self.wgOptical, "btn_renameFolders"):
			self.wgOptical.btn_renameFolders.clicked.connect(self.press_renameFolders)

		if hasattr(self.wgOptical, "btn_autoRun"):
			self.wgOptical.btn_autoRun.clicked.connect(self.press_autoRun)

		# ----------------------------------------------------------------------
		# LIST VIEW SETUP
		self.wgOptical.list_folders.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
		self.wgOptical.list_folders.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
		self.wgOptical.list_folders.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
		self.wgOptical.list_folders.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
		self.wgOptical.list_folders.setFrameShape(QtWidgets.QFrame.NoFrame)

		# ----------------------------------------------------------------------
		# INITIAL STATE
		self.update_target_folder_state("")
		self.set_folder_empty_state()
		self.set_preview_empty_state()
		self.wgOptical.lineEdit_textInput.clear()

		# STARTUP PATH SUPPORT
		if len(sys.argv) > 1:
			startup_path = sys.argv[1]
			if os.path.isdir(startup_path):
				self.set_target_folder(startup_path)

		# DISPLAY
		self.wgOptical.show()

	# =============================
	# FOLDER PANEL STATES
	# =============================

	def set_folder_empty_state(self, text="Check target has content"):
		self.wgOptical.stackedWidget_folders.setCurrentWidget(
			self.wgOptical.page_emptyFolderList
		)

		if hasattr(self.wgOptical, "label_listEmptyDetail"):
			self.wgOptical.label_listEmptyDetail.setText(text)

	def set_folder_list_state(self):
		self.wgOptical.stackedWidget_folders.setCurrentWidget(
			self.wgOptical.page_folderList
		)

	# =============================
	# PREVIEW PANEL STATES
	# =============================

	def set_preview_empty_state(self, text="Select a folder"):
		self.wgOptical.stackedWidget_preview.setCurrentWidget(
			self.wgOptical.page_previewEmpty
		)

		if hasattr(self.wgOptical, "label_previewEmptyDetail"):
			self.wgOptical.label_previewEmptyDetail.setText(text)

		if hasattr(self.wgOptical, "label_originalFolderName"):
			self.wgOptical.label_originalFolderName.hide()

		# Hide status indicator dot
		if hasattr(self.wgOptical, "label_statusDot"):
			self.wgOptical.label_statusDot.hide()

		# Clear and hide thumbnail strip
		if hasattr(self.wgOptical, "thumbnailStrip"):
			self.wgOptical.thumbnailStrip.clear()
			self.wgOptical.thumbnailStrip.hide()

	def set_preview_image_state(self):
		self.wgOptical.stackedWidget_preview.setCurrentWidget(
			self.wgOptical.page_previewImage
		)

	# ******************************************************************************
	# PREVIEW HELPERS

	def update_folder_list_selection_ui(self):
		current_row = self.wgOptical.list_folders.currentRow()

		for row in range(self.wgOptical.list_folders.count()):
			item = self.wgOptical.list_folders.item(row)
			if not item:
				continue

			widget = self.wgOptical.list_folders.itemWidget(item)
			if not widget:
				continue

			widget.set_selected(row == current_row)

	def warm_nearby_preview_cache(self, radius=3):
		if not self.current_folder_images:
			return

		if not hasattr(self, "display_preview_cache"):
			self.display_preview_cache = {}

		start = max(0, self.current_image_index - radius)
		end = min(len(self.current_folder_images), self.current_image_index + radius + 1)

		keep_paths = set(self.current_folder_images[start:end])

		keys_to_remove = [key for key in self.display_preview_cache if key[0] not in keep_paths]
		for key in keys_to_remove:
			del self.display_preview_cache[key]

		for image_path in self.current_folder_images[start:end]:
			self.get_display_preview_pixmap(image_path)

	def get_display_preview_pixmap(self, image_path, max_width=1800, max_height=1800):
		cache_key = (image_path, max_width, max_height)

		if not hasattr(self, "display_preview_cache"):
			self.display_preview_cache = {}

		if cache_key in self.display_preview_cache:
			return self.display_preview_cache[cache_key]

		reader = QtGui.QImageReader(image_path)
		if not reader.canRead():
			return QtGui.QPixmap()

		image_size = reader.size()
		if image_size.isValid():
			scale = min(
				max_width / max(1, image_size.width()),
				max_height / max(1, image_size.height()),
				1.0
			)
			target_size = QtCore.QSize(
				max(1, int(image_size.width() * scale)),
				max(1, int(image_size.height() * scale))
			)
			reader.setScaledSize(target_size)

		image = reader.read()
		if image.isNull():
			return QtGui.QPixmap()

		pixmap = QtGui.QPixmap.fromImage(image)
		self.display_preview_cache[cache_key] = pixmap

		# keep cache small
		if len(self.display_preview_cache) > 20:
			first_key = next(iter(self.display_preview_cache))
			del self.display_preview_cache[first_key]

		return pixmap


	def on_thumbnail_clicked(self, item):
		if not item:
			return

		image_path = item.data(QtCore.Qt.UserRole)
		if not image_path:
			return

		if image_path in self.current_folder_images:
			self.current_image_index = self.current_folder_images.index(image_path)

		self.show_image(image_path)

	def update_thumbnail_selection_ui(self):
		if not hasattr(self.wgOptical, "thumbnailStrip"):
			return

		strip = self.wgOptical.thumbnailStrip

		for row in range(strip.count()):
			item = strip.item(row)
			if not item:
				continue

			widget = strip.itemWidget(item)
			if not widget:
				continue

			widget.set_selected(row == self.current_image_index)

	def update_thumbnail_strip(self):
		if not hasattr(self.wgOptical, "thumbnailStrip"):
			return

		strip = self.wgOptical.thumbnailStrip
		strip.clear()

		if not self.current_folder_images:
			strip.hide()
			return

		for index, image_path in enumerate(self.current_folder_images):
			item = QtWidgets.QListWidgetItem()
			item.setData(QtCore.Qt.UserRole, image_path)
			item.setToolTip(os.path.basename(image_path))
			item.setSizeHint(QtCore.QSize(112, 68))
			strip.addItem(item)

			pixmap = self.get_thumbnail_pixmap(image_path)
			widget = ThumbnailItemWidget(
				pixmap=pixmap,
				selected=(index == self.current_image_index)
			)
			strip.setItemWidget(item, widget)

		if 0 <= self.current_image_index < strip.count():
			strip.setCurrentRow(self.current_image_index)
			strip.scrollToItem(strip.item(self.current_image_index))

		strip.show()


	def _insert_thumbnail_strip_recursive(self, layout):
		for i in range(layout.count()):
			item = layout.itemAt(i)

			if item.widget() is self.wgOptical.row_textEdit:
				layout.insertWidget(i, self.wgOptical.thumbnailStrip)
				return True

			child_layout = item.layout()
			if child_layout is not None:
				if self._insert_thumbnail_strip_recursive(child_layout):
					return True

		return False

	def update_preview_status_indicator(self):
		if not hasattr(self.wgOptical, "label_statusDot"):
			return

		dot = self.wgOptical.label_statusDot

		if not self.current_folder_path:
			dot.hide()
			return

		record = self.folder_records.get(self.current_folder_path, {})
		status = record.get("status", "pending")

		color_map = {
			"confirmed": "#4CAF50",
			"pending": "#FF9800",
			"ignored": "#F44336",
		}
		color = color_map.get(status, "#777777")

		dot.setStyleSheet(f"""
			background-color: {color};
			border: 2px solid #1f1f1f;
			border-radius: 8px;
		""")

		effect = QtWidgets.QGraphicsDropShadowEffect()
		effect.setBlurRadius(12)
		effect.setOffset(0, 0)
		effect.setColor(QtGui.QColor(color))

		dot.setGraphicsEffect(effect)

		self.position_folder_overlay()

	def select_previous_folder(self):
		row = self.wgOptical.list_folders.currentRow()
		if row > 0:
			self.wgOptical.list_folders.setCurrentRow(row - 1)

	def select_next_folder(self):
		row = self.wgOptical.list_folders.currentRow()
		if row < self.wgOptical.list_folders.count() - 1:
			self.wgOptical.list_folders.setCurrentRow(row + 1)

	def show_previous_image(self):
		if not self.current_folder_images:
			return

		if self.current_image_index > 0:
			self.current_image_index -= 1
			self.show_image(self.current_folder_images[self.current_image_index])

	def show_next_image(self):
		if not self.current_folder_images:
			return

		if self.current_image_index < len(self.current_folder_images) - 1:
			self.current_image_index += 1
			self.show_image(self.current_folder_images[self.current_image_index])

	def show_info_dialog(self, title, heading, detail="", sub_detail=""):
		dialog = CustomMessageDialog(
			title=title,
			heading=heading,
			detail=detail,
			sub_detail=sub_detail,
			parent=self.wgOptical
		)
		dialog.exec()

	def show_confirm_dialog(self, title, heading, detail="", sub_detail="", confirm_text="Continue"):
		dialog = ConfirmActionDialog(
			title=title,
			heading=heading,
			detail=detail,
			sub_detail=sub_detail,
			confirm_text=confirm_text,
			parent=self.wgOptical
		)
		return dialog.exec() == QtWidgets.QDialog.Accepted

	def save_current_folder_text(self):
		if not self.current_folder_path:
			return

		text = self.wgOptical.lineEdit_textInput.text().strip()
		self.folder_name_edits[self.current_folder_path] = text

	def on_text_input_changed(self, text):
		if not self.current_folder_path:
			return

		clean_text = text.strip()
		self.folder_name_edits[self.current_folder_path] = clean_text

		record = self.folder_records.get(self.current_folder_path)
		if not record:
			return

		approved_name = record.get("approved_name", "").strip()

		if clean_text == approved_name and clean_text:
			record["status"] = "confirmed"
		else:
			record["status"] = "pending"

		self.update_folder_item_ui(self.current_folder_path)
		self.update_preview_status_indicator()

	def load_current_folder_text(self, folder_path):
		if not folder_path:
			self.wgOptical.lineEdit_textInput.blockSignals(True)
			self.wgOptical.lineEdit_textInput.clear()
			self.wgOptical.lineEdit_textInput.setPlaceholderText("")
			self.wgOptical.lineEdit_textInput.blockSignals(False)
			return

		record = self.folder_records.get(folder_path, {})
		approved_name = record.get("approved_name", "").strip()
		suggested_name = record.get("suggested_name", "").strip()
		current_name = os.path.basename(folder_path)

		self.wgOptical.lineEdit_textInput.blockSignals(True)

		if approved_name:
			self.wgOptical.lineEdit_textInput.setText(approved_name)
		elif suggested_name:
			self.wgOptical.lineEdit_textInput.setText(suggested_name)
		else:
			self.wgOptical.lineEdit_textInput.clear()

		self.wgOptical.lineEdit_textInput.setPlaceholderText(current_name)
		self.wgOptical.lineEdit_textInput.blockSignals(False)

	def finish_preview_resize(self):
		self.is_resizing_preview = False

		if self.preview_pixmap_item.pixmap().isNull():
			if hasattr(self.wgOptical, "label_originalFolderName"):
				self.wgOptical.label_originalFolderName.hide()
			return

		self.update_preview_canvas_geometry()

		if hasattr(self.wgOptical, "label_originalFolderName") and self.current_folder_path:
			label = self.wgOptical.label_originalFolderName
			label.setText(os.path.basename(self.current_folder_path))
			label.adjustSize()
			label.show()
			self.position_folder_overlay()

	def position_folder_overlay(self):
		if self.is_resizing_preview:
			return

		if not hasattr(self.wgOptical, "label_originalFolderName"):
			return
		if not hasattr(self.wgOptical, "previewCanvas"):
			return
		if not hasattr(self.wgOptical, "imageContainer"):
			return
		if not hasattr(self.wgOptical, "label_statusDot"):
			return

		label = self.wgOptical.label_originalFolderName
		dot = self.wgOptical.label_statusDot
		canvas = self.wgOptical.previewCanvas
		container = self.wgOptical.imageContainer
		view = self.wgOptical.imageView
		viewport = view.viewport()

		pixmap = self.preview_pixmap_item.pixmap()
		if pixmap.isNull():
			label.hide()
			dot.hide()
			return

		if label.parent() is not canvas:
			label.setParent(canvas)

		if dot.parent() is not canvas:
			dot.setParent(canvas)

		label.setWordWrap(False)
		label.adjustSize()

		scene_rect = self.preview_pixmap_item.sceneBoundingRect()
		view_rect = view.mapFromScene(scene_rect).boundingRect()
		view_rect = view_rect.intersected(viewport.rect())

		if view_rect.isEmpty():
			label.hide()
			dot.hide()
			return

		top_left_in_container = viewport.mapTo(container, view_rect.topLeft())
		top_right_in_container = viewport.mapTo(container, view_rect.topRight())

		top_left_in_canvas = container.pos() + top_left_in_container
		top_right_in_canvas = container.pos() + top_right_in_container

		margin = 6

		label_x = int(top_right_in_canvas.x() - label.width() - margin)
		label_y = int(top_left_in_canvas.y() + margin)

		label_x = max(0, min(label_x, canvas.width() - label.width()))
		label_y = max(0, min(label_y, canvas.height() - label.height()))

		label.move(label_x, label_y)
		label.raise_()
		label.show()

		dot_x = label_x - dot.width() - 8
		dot_y = label_y + (label.height() - dot.height()) // 2

		dot_x = max(0, min(dot_x, canvas.width() - dot.width()))
		dot_y = max(0, min(dot_y, canvas.height() - dot.height()))

		dot.move(dot_x, dot_y)
		dot.raise_()
		dot.show()

	def clear_preview_pixmap(self):
		self.preview_zoom = 0
		self.preview_pixmap_item.setPixmap(QtGui.QPixmap())
		self.preview_scene.setSceneRect(QtCore.QRectF())
		self.wgOptical.imageView.resetTransform()
		self.wgOptical.imageView.setDragMode(QtWidgets.QGraphicsView.NoDrag)

		if hasattr(self.wgOptical, "label_originalFolderName"):
			self.wgOptical.label_originalFolderName.hide()

	def set_preview_pixmap(self, pixmap):
		if pixmap.isNull():
			self.clear_preview_pixmap()
			return

		self.preview_zoom = 0
		self.preview_pixmap_item.setPixmap(pixmap)
		self.preview_scene.setSceneRect(QtCore.QRectF(pixmap.rect()))
		self.wgOptical.imageView.setDragMode(QtWidgets.QGraphicsView.NoDrag)

		QtCore.QTimer.singleShot(0, self.update_preview_canvas_geometry)

	def fit_preview_image(self):
		pixmap = self.preview_pixmap_item.pixmap()
		if pixmap.isNull():
			return

		view = self.wgOptical.imageView
		view_rect = view.viewport().rect()
		if view_rect.isEmpty() or view_rect.width() < 2 or view_rect.height() < 2:
			return

		view.resetTransform()
		view.setSceneRect(self.preview_pixmap_item.boundingRect())
		view.fitInView(self.preview_pixmap_item, QtCore.Qt.KeepAspectRatio)
		view.centerOn(self.preview_pixmap_item)

	def reset_preview_zoom(self):
		if self.preview_pixmap_item.pixmap().isNull():
			return

		self.preview_zoom = 0
		self.wgOptical.imageView.setDragMode(QtWidgets.QGraphicsView.NoDrag)
		self.fit_preview_image()
		self.position_folder_overlay()

	def handle_preview_wheel(self, event):
		if self.preview_pixmap_item.pixmap().isNull():
			return False

		if event.angleDelta().y() > 0:
			factor = 1.15
			self.preview_zoom += 1

			if self.preview_zoom > 20:
				self.preview_zoom = 20
				return True

			self.wgOptical.imageView.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
			self.wgOptical.imageView.scale(factor, factor)

		else:
			self.preview_zoom -= 1

			if self.preview_zoom <= 0:
				self.preview_zoom = 0
				self.wgOptical.imageView.setDragMode(QtWidgets.QGraphicsView.NoDrag)
				self.fit_preview_image()
				return True

			self.wgOptical.imageView.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
			self.wgOptical.imageView.scale(1 / 1.15, 1 / 1.15)

		return True

	def update_preview_canvas_geometry(self):
		if not hasattr(self.wgOptical, "previewStage") or not hasattr(self.wgOptical, "previewCanvas"):
			self.fit_preview_image()
			return

		stage = self.wgOptical.previewStage
		canvas = self.wgOptical.previewCanvas

		stage_rect = stage.contentsRect()
		if stage_rect.width() < 2 or stage_rect.height() < 2:
			return

		target_width = stage_rect.width()
		target_height = int(target_width * 2 / 3)

		if target_height > stage_rect.height():
			target_height = stage_rect.height()
			target_width = int(target_height * 3 / 2)

		x = stage_rect.x() + (stage_rect.width() - target_width) // 2
		y = stage_rect.y() + (stage_rect.height() - target_height) // 2

		canvas.setGeometry(x, y, target_width, target_height)
		canvas.raise_()

		if hasattr(self.wgOptical, "imageContainer"):
			margin = 8
			self.wgOptical.imageContainer.setGeometry(
				margin,
				margin,
				max(1, target_width - (margin * 2)),
				max(1, target_height - (margin * 2))
			)

		self.fit_preview_image()

	# ******************************************************************************
	# DATA HELPERS

	def get_thumbnail_pixmap(self, image_path, width=96, height=44):
		cache_key = (image_path, width, height)

		if cache_key in self.thumbnail_icon_cache:
			return self.thumbnail_icon_cache[cache_key]

		reader = QtGui.QImageReader(image_path)
		if not reader.canRead():
			return QtGui.QPixmap()

		image_size = reader.size()
		if image_size.isValid():
			scale = min(
				width / max(1, image_size.width()),
				height / max(1, image_size.height()),
				1.0
			)
			target_size = QtCore.QSize(
				max(1, int(image_size.width() * scale)),
				max(1, int(image_size.height() * scale))
			)
			reader.setScaledSize(target_size)

		image = reader.read()
		if image.isNull():
			return QtGui.QPixmap()

		pixmap = QtGui.QPixmap.fromImage(image)
		self.thumbnail_icon_cache[cache_key] = pixmap
		return pixmap

	def set_auto_run_button_state(self, running=False):
		if not hasattr(self.wgOptical, "btn_autoRun"):
			return

		button = self.wgOptical.btn_autoRun

		if running:
			button.setText("RUNNING...")
			button.setEnabled(False)
			button.setStyleSheet("""
				QPushButton#btn_autoRun {
					background-color: #C62828;
					color: #ededed;
					border: none;
					border-radius: 3px;
					padding: 4px 10px;
					font-weight: 600;
				}
			""")
		else:
			button.setText("AUTO-RUN")
			button.setEnabled(True)
			button.setStyleSheet("")

	def get_subfolders(self, folder_path):
		if not folder_path or not os.path.isdir(folder_path):
			return []

		folders = []
		for name in os.listdir(folder_path):
			full = os.path.join(folder_path, name)
			if os.path.isdir(full):
				folders.append(full)

		return sorted(folders, key=lambda x: os.path.basename(x).lower())

	def get_images_in_folder(self, folder_path):
		if not folder_path or not os.path.isdir(folder_path):
			return []

		valid_exts = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}

		images = []
		for name in os.listdir(folder_path):
			full = os.path.join(folder_path, name)
			ext = os.path.splitext(name)[1].lower()

			if os.path.isfile(full) and ext in valid_exts:
				images.append(full)

		return sorted(images, key=lambda x: os.path.basename(x).lower())

	def get_ocr_acceleration_backend(self):
		try:
			import torch

			if torch.cuda.is_available():
				return "cuda"

			if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
				return "mps"

			return "cpu"

		except Exception:
			return "cpu"

	def is_ocr_gpu_available(self):
		try:
			import torch

			# CUDA (Windows / Linux NVIDIA)
			if torch.cuda.is_available():
				return True

			# MPS (Mac Apple Silicon)
			if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
				return True

			return False

		except Exception:
			return False

	def confirm_cpu_ocr_fallback_if_needed(self):
		backend = self.get_ocr_acceleration_backend()

		if backend in ("cuda", "mps"):
			return True

		return self.show_confirm_dialog(
			title="No GPU Acceleration Detected",
			heading="Run OCR Without GPU Acceleration?",
			detail="No compatible CUDA or Apple Metal acceleration was detected.",
			sub_detail="OCR can still run on CPU, but it may take significantly longer on larger folders. Continue anyway?",
			confirm_text="Continue Anyway"
		)

	def get_ocr_candidate_images(self, folder_path):
		images = self.get_images_in_folder(folder_path)
		if not images:
			return []

		mode = self.ocr_settings.get("mode", "last")
		padding = max(1, int(self.ocr_settings.get("padding", 5)))

		if mode == "first":
			return images[:1]

		if mode == "last":
			return list(reversed(images[-1:]))

		if mode == "first_n":
			return images[:padding]

		if mode == "last_n":
			return list(reversed(images[-padding:]))

		if mode == "all":
			return list(reversed(images))

		return list(reversed(images[-1:]))

	def sanitize_folder_name(self, text):
		text = text.strip()
		text = re.sub(r'[<>:"/\\|?*]', "", text)
		text = re.sub(r"\s+", " ", text)
		return text.strip(" .")

	def update_folder_item_ui(self, folder_path):
		for row in range(self.wgOptical.list_folders.count()):
			item = self.wgOptical.list_folders.item(row)
			if not item:
				continue

			item_folder_path = item.data(QtCore.Qt.UserRole)
			if item_folder_path != folder_path:
				continue

			widget = self.wgOptical.list_folders.itemWidget(item)
			if not widget:
				return

			record = self.folder_records.get(folder_path, {})
			status = record.get("status", "pending")
			name = os.path.basename(folder_path)
			suggested_name = record.get("approved_name", "") or record.get("suggested_name", "")

			widget.name_label.setText(name)
			widget.set_suggested_name(suggested_name)
			widget.set_status(status)
			return

	def populate_folder_list(self, folder_path):
		self.wgOptical.list_folders.clear()

		self.current_folder_path = ""
		self.current_folder_images = []
		self.current_image_index = 0

		if not folder_path or not os.path.isdir(folder_path):
			self.set_folder_empty_state()
			self.set_preview_empty_state()
			return

		subfolders = self.get_subfolders(folder_path)

		if not subfolders:
			self.set_folder_empty_state("Check target has content")
			self.set_preview_empty_state("No folders available")
			return

		for folder in subfolders:
			name = os.path.basename(folder)

			if folder not in self.folder_records:
				self.folder_records[folder] = {
					"original_name": name,
					"suggested_name": "",
					"approved_name": "",
					"status": "pending",
					"ocr_source_image": "",
				}

			if folder not in self.folder_name_edits:
				self.folder_name_edits[folder] = self.folder_records[folder].get("approved_name", "")

			item = QtWidgets.QListWidgetItem()
			item.setData(QtCore.Qt.UserRole, folder)

			record = self.folder_records[folder]
			status = record.get("status", "pending")
			suggested_name = record.get("approved_name", "") or record.get("suggested_name", "")

			widget = FolderItemWidget(
				original_name=name,
				suggested_name=suggested_name,
				status=status
			)

			item.setSizeHint(QtCore.QSize(0, 56))
			self.wgOptical.list_folders.addItem(item)
			self.wgOptical.list_folders.setItemWidget(item, widget)

		self.set_folder_list_state()
		self.wgOptical.list_folders.setCurrentRow(0)
		self.update_folder_list_selection_ui()

	def set_target_folder(self, folder_path):
		self.current_target_folder = folder_path if folder_path else ""

		self.wgOptical.input_targetFolder.setText(self.current_target_folder)
		self.wgOptical.input_targetFolder.setToolTip(self.current_target_folder)
		self.update_target_folder_state(self.current_target_folder)

		self.populate_folder_list(self.current_target_folder)

	def update_target_folder_state(self, folder_path=""):
		if folder_path and os.path.isdir(folder_path):
			state = "valid"
		else:
			state = "missing"

		widgets = [
			self.wgOptical.frame_inputTargetFolder,   # ← NEW (important)
			self.wgOptical.input_targetFolder,
			self.wgOptical.btn_browseTargetFolder,
		]

		for widget in widgets:
			widget.setProperty("pathState", state)
			widget.style().unpolish(widget)
			widget.style().polish(widget)
			widget.update()
	# ******************************************************************************
	# FOLDER / IMAGE SELECTION

	def on_folder_selected(self, row):
		if row < 0:
			self.current_folder_path = ""
			self.current_folder_images = []
			self.current_image_index = 0
			self.clear_preview_pixmap()
			self.set_preview_empty_state("Select a folder")
			self.wgOptical.lineEdit_textInput.clear()
			return

		item = self.wgOptical.list_folders.item(row)
		if not item:
			self.clear_preview_pixmap()
			self.set_preview_empty_state("Select a folder")
			self.wgOptical.lineEdit_textInput.clear()
			return

		self.save_current_folder_text()

		folder_path = item.data(QtCore.Qt.UserRole)
		self.current_folder_path = folder_path
		self.load_current_folder_text(folder_path)

		if hasattr(self.wgOptical, "label_originalFolderName"):
			self.wgOptical.label_originalFolderName.setText(os.path.basename(folder_path))
			self.wgOptical.label_originalFolderName.hide()

		self.update_preview_status_indicator()
		self.show_folder_preview(folder_path)
		self.update_folder_list_selection_ui()

	def move_to_next_folder(self):
		current_row = self.wgOptical.list_folders.currentRow()
		if current_row < self.wgOptical.list_folders.count() - 1:
			self.wgOptical.list_folders.setCurrentRow(current_row + 1)

	def show_folder_preview(self, folder_path):
		images = self.get_images_in_folder(folder_path)
		self.preview_pixmap_cache.clear()

		if not images:
			self.current_folder_images = []
			self.current_image_index = 0
			self.clear_preview_pixmap()
			self.set_preview_empty_state("No images in folder")
			if hasattr(self.wgOptical, "thumbnailStrip"):
				self.wgOptical.thumbnailStrip.clear()
				self.wgOptical.thumbnailStrip.hide()
			return

		self.current_folder_images = images

		record = self.folder_records.get(folder_path, {})
		ocr_source_image = record.get("ocr_source_image", "")

		if ocr_source_image and ocr_source_image in images:
			self.current_image_index = images.index(ocr_source_image)
		else:
			self.current_image_index = len(images) - 1

		self.set_preview_image_state()
		self.update_thumbnail_strip()

		QtCore.QTimer.singleShot(0, self.update_preview_canvas_geometry)
		QtCore.QTimer.singleShot(
			0,
			lambda: self.show_image(self.current_folder_images[self.current_image_index])
		)

	def show_image(self, image_path):
		pixmap = self.get_display_preview_pixmap(image_path)

		if pixmap.isNull():
			self.clear_preview_pixmap()
			self.set_preview_empty_state("Failed to load image")
			return

		if image_path in self.current_folder_images:
			self.current_image_index = self.current_folder_images.index(image_path)

		if hasattr(self.wgOptical, "label_originalFolderName"):
			self.wgOptical.label_originalFolderName.hide()

		if hasattr(self.wgOptical, "label_statusDot"):
			self.wgOptical.label_statusDot.hide()

		self.set_preview_pixmap(pixmap)
		self.overlay_resize_timer.start(40)

		if hasattr(self.wgOptical, "thumbnailStrip"):
			strip = self.wgOptical.thumbnailStrip
			if 0 <= self.current_image_index < strip.count():
				strip.blockSignals(True)
				strip.setCurrentRow(self.current_image_index)
				strip.scrollToItem(strip.item(self.current_image_index))
				strip.blockSignals(False)

		self.update_thumbnail_selection_ui()
		self.warm_nearby_preview_cache(radius=3)

	# ******************************************************************************
	# EVENTS

	def resize_preview(self):
		if self.preview_pixmap_item.pixmap().isNull():
			return

		self.is_resizing_preview = True

		if hasattr(self.wgOptical, "label_originalFolderName"):
			self.wgOptical.label_originalFolderName.hide()

		if hasattr(self.wgOptical, "label_statusDot"):
			self.wgOptical.label_statusDot.hide()

		self.update_preview_canvas_geometry()
		self.overlay_resize_timer.start(120)

	# ******************************************************************************
	# OCR / REVIEW / RENAME

	def ensure_ocr_module(self, progress_dialog=None):
		if self._ocr_module is not None:
			return self._ocr_module

		try:
			if progress_dialog is not None:
				progress_dialog.set_heading("Initializing OCR...")
				progress_dialog.set_detail("Preparing OCR engine...")
				progress_dialog.set_sub_detail("Loading EasyOCR and model data.")
				QtWidgets.QApplication.processEvents()

			self._ocr_module = importlib.import_module("optical_ocr")
			return self._ocr_module

		except Exception as error:
			QtWidgets.QMessageBox.critical(
				self.wgOptical,
				"OCR Load Failed",
				f"Could not initialize OCR.\n\n{error}"
			)
			self._ocr_module = None
			return None

	def run_ocr_on_image(self, image_path):
		module = self.ensure_ocr_module()
		if module is None:
			return ""

		try:
			result = module.fetch_slate_data(image_path)
			return result or ""
		except Exception as error:
			print(f"OCR failed for {image_path}: {error}")
			return ""

	def is_valid_detected_label(self, text):
		if not text:
			return False

		text = text.strip().upper()

		if len(text) < 3:
			return False

		if not re.search(r'[A-Z]', text):
			return False

		valid_count = sum(ch.isalnum() or ch == '_' for ch in text)
		if valid_count < max(3, int(len(text) * 0.6)):
			return False

		return True

	def run_ocr_on_folder(self, folder_path):
		candidates = self.get_ocr_candidate_images(folder_path)
		if not candidates:
			return "", None

		stop_on_first_hit = self.ocr_settings.get("stop_on_first_hit", True)

		best_text = ""
		best_image = None

		for image_path in candidates:
			text = self.run_ocr_on_image(image_path).strip()

			if not self.is_valid_detected_label(text):
				continue

			best_text = text
			best_image = image_path

			if stop_on_first_hit:
				break

		return best_text, best_image

	def press_autoRun(self):
		if not self.current_target_folder or not os.path.isdir(self.current_target_folder):
			return

		subfolders = self.get_subfolders(self.current_target_folder)
		if not subfolders:
			return

		if not self.confirm_cpu_ocr_fallback_if_needed():
			return

		self.set_auto_run_button_state(True)

		progress = OCRProgressDialog(
			title="Auto-Run OCR",
			heading="Initializing OCR...",
			detail="Preparing OCR engine...",
			parent=self.wgOptical
		)
		progress.set_sub_detail("Loading OCR engine and preparing folder scan.")
		progress.set_progress(0, len(subfolders))
		progress.show()
		QtWidgets.QApplication.processEvents()

		try:
			module = self.ensure_ocr_module(progress)
			if module is None:
				progress.close()
				return

			for index, folder_path in enumerate(subfolders, start=1):
				if progress.was_canceled():
					break

				progress.set_heading("Running OCR Detection")
				progress.set_detail(f"Scanning folder {index} of {len(subfolders)}")
				progress.set_sub_detail(os.path.basename(folder_path))
				progress.set_progress(index - 1, len(subfolders))
				QtWidgets.QApplication.processEvents()

				ocr_text, matched_image = self.run_ocr_on_folder(folder_path)

				self.folder_ocr_suggestions[folder_path] = ocr_text

				record = self.folder_records.get(folder_path, {})
				record["suggested_name"] = ocr_text
				record["ocr_source_image"] = matched_image or ""

				if ocr_text:
					record["approved_name"] = ocr_text
					record["status"] = "confirmed"
					self.folder_name_edits[folder_path] = ocr_text
				else:
					record["approved_name"] = ""
					record["status"] = "pending"
					self.folder_name_edits[folder_path] = ""

				self.folder_records[folder_path] = record
				self.update_folder_item_ui(folder_path)

				progress.set_progress(index, len(subfolders))
				QtWidgets.QApplication.processEvents()

		finally:
			progress.close()
			self.set_auto_run_button_state(False)

		if self.current_folder_path:
			self.load_current_folder_text(self.current_folder_path)
			self.update_preview_status_indicator()
			QtCore.QTimer.singleShot(0, lambda: self.show_folder_preview(self.current_folder_path))

		#self.wgOptical.input_targetFolder.deselect()
		self.wgOptical.btn_autoRun.setFocus()

	def press_confirm(self):
		if not self.current_folder_path:
			return

		text = self.sanitize_folder_name(self.wgOptical.lineEdit_textInput.text())

		self.wgOptical.lineEdit_textInput.blockSignals(True)
		self.wgOptical.lineEdit_textInput.setText(text)
		self.wgOptical.lineEdit_textInput.blockSignals(False)

		self.folder_name_edits[self.current_folder_path] = text
		self.folder_records[self.current_folder_path]["approved_name"] = text

		if text:
			self.folder_records[self.current_folder_path]["status"] = "confirmed"
		else:
			self.folder_records[self.current_folder_path]["status"] = "pending"

		self.update_folder_item_ui(self.current_folder_path)
		self.update_preview_status_indicator()
		self.move_to_next_folder()

	def press_ignore(self):
		if not self.current_folder_path:
			return

		self.folder_name_edits[self.current_folder_path] = ""
		self.folder_records[self.current_folder_path]["approved_name"] = ""
		self.folder_records[self.current_folder_path]["status"] = "ignored"

		self.wgOptical.lineEdit_textInput.blockSignals(True)
		self.wgOptical.lineEdit_textInput.clear()
		self.wgOptical.lineEdit_textInput.blockSignals(False)

		self.update_folder_item_ui(self.current_folder_path)
		self.update_preview_status_indicator()
		self.move_to_next_folder()

	def press_renameFolders(self):
		self.save_current_folder_text()

		renamed_paths = {}
		current_selection_new_path = self.current_folder_path

		renamed_count = 0
		skipped_count = 0
		failed_count = 0

		for folder_path, record in list(self.folder_records.items()):
			status = record.get("status", "pending")
			new_name = self.sanitize_folder_name(record.get("approved_name", ""))

			if status != "confirmed" or not new_name:
				skipped_count += 1
				continue

			old_name = os.path.basename(folder_path)
			if new_name == old_name:
				skipped_count += 1
				continue

			parent_dir = os.path.dirname(folder_path)
			new_path = os.path.join(parent_dir, new_name)

			if os.path.exists(new_path):
				failed_count += 1
				continue

			try:
				os.rename(folder_path, new_path)
			except Exception:
				failed_count += 1
				continue

			renamed_paths[folder_path] = new_path
			renamed_count += 1

			record["original_name"] = new_name
			self.folder_records[new_path] = record
			del self.folder_records[folder_path]

			if folder_path in self.folder_name_edits:
				self.folder_name_edits[new_path] = self.folder_name_edits.pop(folder_path)

			if folder_path in self.folder_ocr_suggestions:
				self.folder_ocr_suggestions[new_path] = self.folder_ocr_suggestions.pop(folder_path)

			if current_selection_new_path == folder_path:
				current_selection_new_path = new_path

		if renamed_paths:
			self.current_folder_path = current_selection_new_path
			self.populate_folder_list(self.current_target_folder)

			if self.current_folder_path:
				for row in range(self.wgOptical.list_folders.count()):
					item = self.wgOptical.list_folders.item(row)
					if item and item.data(QtCore.Qt.UserRole) == self.current_folder_path:
						self.wgOptical.list_folders.setCurrentRow(row)
						break

		if renamed_count > 0:
			self.show_info_dialog(
				title="Rename Complete",
				heading="Folders Renamed",
				detail=f"{renamed_count} folder(s) renamed.",
				sub_detail=f"Skipped: {skipped_count}    Failed: {failed_count}"
			)
		else:
			self.show_info_dialog(
				title="No Changes Made",
				heading="No Folders Renamed",
				detail="No confirmed folder names required renaming.",
				sub_detail=f"Skipped: {skipped_count}    Failed: {failed_count}"
			)

	# ******************************************************************************
	# PRESS FUNCTIONS

	def press_browseTargetFolder(self):
		current_path = self.wgOptical.input_targetFolder.text().strip()

		folder = QtWidgets.QFileDialog.getExistingDirectory(
			self.wgOptical,
			"Select Target Folder",
			current_path if current_path else ""
		)

		if folder:
			self.set_target_folder(folder)


# *********************************************************************#
# START UI
if __name__ == "__main__":
	try:
		app = QtWidgets.QApplication(sys.argv)
		initialize_app = Optical()
		app.exec()

	except Exception as error:
		import traceback
		traceback.print_exc()
		input("Press Enter to close...")