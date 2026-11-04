import ast
from pathlib import Path

from hardware.camera import Camera
from hardware.mock_camera import MockCamera
from hardware.mock_motor import MockMotor
from hardware.motor import Motor

HARDWARE_DIR = Path(__file__).resolve().parents[1] / "hardware"
FORBIDDEN = {"picamera2", "RPi", "gpiozero", "pigpio", "lgpio", "smbus", "cv2", "paho"}


def deal_one_card(camera: Camera, motor: Motor) -> bytes:
    """模擬上層邏輯：只透過介面方法操作。"""
    frame = camera.capture()
    motor.rotate(30)
    motor.stop()
    return frame


def test_upper_layer_works_with_interfaces_only():
    camera, motor = MockCamera(frames=[b"x"]), MockMotor()

    assert deal_one_card(camera, motor) == b"x"
    assert [action.name for action in motor.actions] == ["rotate", "stop"]


def test_hardware_package_imports_no_hardware_library():
    imported: set[str] = set()
    for path in HARDWARE_DIR.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imported |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported.add(node.module.split(".")[0])

    assert imported.isdisjoint(FORBIDDEN)
