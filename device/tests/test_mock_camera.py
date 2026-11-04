from hardware.camera import Camera
from hardware.mock_camera import TEST_FRAME, MockCamera


def test_mock_camera_returns_fixed_test_frame_by_default():
    camera = MockCamera()

    assert camera.capture() == TEST_FRAME
    assert camera.capture() == TEST_FRAME


def test_mock_camera_returns_preset_frames_in_order():
    camera = MockCamera(frames=[b"a", b"b"])

    assert [camera.capture() for _ in range(3)] == [b"a", b"b", b"a"]


def test_mock_camera_satisfies_camera_interface():
    assert isinstance(MockCamera(), Camera)
