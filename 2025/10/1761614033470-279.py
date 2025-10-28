import sys
import cv2
import threading
import os
import logging
from PyQt5.QtWidgets import (QApplication, QMainWindow, QMessageBox,
                             QLabel, QSizePolicy)
from PyQt5.QtCore import (Qt, QRect, QMutex, pyqtSignal,
                          QObject, QTimer)
from PyQt5.QtGui import (QImage, QPixmap, QPainter,
                         QPen, QColor)
from modules.ui_login import Ui_LoginMain
from modules.face_compare import compare_face, validate_face_image
from PyQt5 import QtCore

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CameraWorker(QObject):
    """摄像头工作线程"""
    frame_ready = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.camera = None
        self.running = False
        self.mutex = QMutex()

    def init_camera(self):
        """初始化摄像头"""
        self.mutex.lock()
        try:
            if self.camera is None:
                backend = cv2.CAP_DSHOW if sys.platform == 'win32' else cv2.CAP_ANY
                self.camera = cv2.VideoCapture(0, backend)

                if not self.camera.isOpened():
                    self.error_occurred.emit("无法打开摄像头")
                    return False

                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
                self.camera.set(cv2.CAP_PROP_FPS, 15)
                self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            return True
        finally:
            self.mutex.unlock()

    def start_capture(self):
        """开始捕获帧"""
        if not self.init_camera():
            return

        self.running = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()

    def _capture_loop(self):
        """捕获循环"""
        while self.running:
            self.mutex.lock()
            if self.camera is None:
                self.mutex.unlock()
                break

            ret, frame = self.camera.read()
            self.mutex.unlock()

            if ret:
                self.frame_ready.emit(frame)
            else:
                self.error_occurred.emit("摄像头读取失败")
                break

            QtCore.QThread.msleep(33)

    def stop_capture(self):
        """停止捕获"""
        self.mutex.lock()
        self.running = False
        if self.camera is not None:
            self.camera.release()
            self.camera = None
        self.mutex.unlock()


class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setFixedSize(1200, 600)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowMaximizeButtonHint)

        # UI初始化
        self.ui = Ui_LoginMain()
        self.ui.setupUi(self)

        # 控件重命名
        self.ui.usernameInput = self.ui.user_line
        self.ui.passwordInput = self.ui.pwd_line
        self.ui.loginButton = self.ui.login_btn
        self.ui.accountLoginBtn = self.ui.acclogin_btn
        self.ui.faceLoginBtn = self.ui.facelogin_btn

        # 摄像头设置
        self.face_rect = QRect(80, 70, 340, 180)
        self.camera_label = QLabel(self.ui.login_box)
        self.camera_label.setGeometry(self.face_rect)
        self.camera_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.camera_label.hide()

        # 初始化摄像头
        self.camera_worker = CameraWorker()
        self.camera_worker.frame_ready.connect(self._update_frame)
        self.camera_worker.error_occurred.connect(self._handle_camera_error)

        # 预加载资源
        self._preload_resources()

        # 连接信号
        self.ui.loginButton.clicked.connect(self._handle_login)
        self.ui.accountLoginBtn.clicked.connect(self._set_account_login_ui)
        self.ui.faceLoginBtn.clicked.connect(self._set_face_login_ui)

        self._set_account_login_ui()

    def _preload_resources(self):
        """预加载资源"""
        # 创建临时目录
        os.makedirs("temp", exist_ok=True)

        # 预加载摄像头驱动
        def _preload_camera():
            cap = cv2.VideoCapture(0)
            if cap.isOpened():
                cap.release()

        threading.Thread(target=_preload_camera, daemon=True).start()

        # 生成占位图
        self.placeholder = QPixmap(self.face_rect.size())
        self.placeholder.fill(QColor(240, 240, 240))
        painter = QPainter(self.placeholder)
        painter.setPen(QPen(Qt.green, 3))
        painter.drawRect(self.placeholder.rect().adjusted(1, 1, -1, -1))
        painter.drawText(self.placeholder.rect(), Qt.AlignCenter, "摄像头初始化中...")
        painter.end()

    def _set_account_login_ui(self):
        """账号登录界面"""
        self.camera_worker.stop_capture()
        self.ui.usernameInput.show()
        self.ui.passwordInput.show()
        self.ui.loginButton.show()
        self.ui.loginButton.setText("登录")
        self.camera_label.hide()
        self.ui.login_box.setStyleSheet("#login_box{background-color: rgba(220, 220, 220,0.5); border-radius:20px;}")
        self.ui.accountLoginBtn.setStyleSheet(
            "font-size:14px; border:none; background-color: rgb(85, 170, 127); color:white; border-radius:15px;")
        self.ui.faceLoginBtn.setStyleSheet(
            "font-size:14px; border:none; background-color: rgb(0, 170, 127); color:white; border-radius:15px;")

    def _set_face_login_ui(self):
        """人脸登录界面"""
        self.ui.usernameInput.hide()
        self.ui.passwordInput.hide()
        self.ui.loginButton.show()
        self.ui.loginButton.setText("登录")
        self.ui.accountLoginBtn.setStyleSheet(
            "font-size:14px; border:none; background-color: rgb(0, 170, 127); color:white; border-radius:15px;")
        self.ui.faceLoginBtn.setStyleSheet(
            "font-size:14px; border:none; background-color: rgb(85, 170, 127); color:white; border-radius:15px;")
        self.camera_label.setPixmap(self.placeholder)
        self.camera_label.show()
        QTimer.singleShot(100, self.camera_worker.start_capture)

    def _update_frame(self, frame):
        """更新画面"""
        try:
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = rgb_image.shape[:2]
            bytes_per_line = 3 * w
            qimage = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimage).scaled(
                self.face_rect.width(),
                self.face_rect.height(),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
            )
            painter = QPainter(pixmap)
            painter.setPen(QPen(Qt.green, 3))
            painter.drawRect(pixmap.rect().adjusted(1, 1, -1, -1))
            painter.end()
            self.camera_label.setPixmap(pixmap)
        except Exception as e:
            logger.error(f"画面更新失败: {str(e)}")

    def _handle_camera_error(self, msg):
        QMessageBox.warning(self, "摄像头错误", msg)
        self._set_account_login_ui()

    def _handle_login(self):
        """处理登录"""
        if "rgb(85, 170, 127)" in self.ui.faceLoginBtn.styleSheet():
            self._capture_and_login()
        else:
            self._account_login()

    def _capture_and_login(self):
        """人脸登录流程"""
        try:
            # 捕获帧
            ret, frame = self.camera_worker.camera.read()
            if not ret:
                raise Exception("无法获取摄像头画面")

            # 保存临时文件
            temp_path = os.path.join("temp", "temp_capture.jpg")
            cv2.imwrite(temp_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 90])

            # 验证图片
            validate_face_image(temp_path)

            # 管理员照片路径
            admin_face = os.path.join("source", "faces", "admin.jpg")
            if not os.path.exists(admin_face):
                raise FileNotFoundError("系统管理员数据缺失")

            # 进行比对
            if compare_face(admin_face, temp_path):
                self._open_main_window()
            else:
                QMessageBox.warning(self, "验证失败", "人脸认证失败")

        except ValueError as e:
            QMessageBox.warning(self, "认证失败", str(e))
        except FileNotFoundError as e:
            QMessageBox.critical(self, "系统错误", str(e))
        except Exception as e:
            logger.error(f"登录异常: {str(e)}")
            QMessageBox.critical(self, "错误", f"登录失败: {str(e)}")
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass

    def _account_login(self):
        """账号登录"""
        username = self.ui.usernameInput.text()
        password = self.ui.passwordInput.text()

        if not username or not password:
            QMessageBox.warning(self, "输入错误", "请输入用户名和密码")
            return

        print(f"登录尝试: 用户={username}")
        self._open_main_window()

    def _open_main_window(self):
        self.camera_worker.stop_capture()
        try:
            # 1. 停止摄像头工作
            self.camera_worker.stop_capture()
            # 2. 创建主窗口实例
            from modules.ui_main import Main_Window
            self.main_window = Main_Window()
            # 3. 显示新窗口前处理未完成事件
            QApplication.processEvents()
            # 4. 显示新窗口并隐藏登录窗口
            self.main_window.show()
            self.close()

        except Exception as e:
            print(f"窗口切换错误: {str(e)}")
            QApplication.quit()

    def closeEvent(self, event):
        self.camera_worker.stop_capture()
        event.accept()


if __name__ == "__main__":
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = LoginWindow()
    window.show()
    sys.exit(app.exec_())
