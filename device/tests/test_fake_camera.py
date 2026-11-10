from hardware.camera import Camera
from hardware.fake_camera import TEST_FRAME, FakeCamera


def test_fake_camera_returns_fixed_test_frame_by_default():
    camera = FakeCamera()

    assert camera.capture() == TEST_FRAME
    assert camera.capture() == TEST_FRAME


def test_fake_camera_returns_preset_frames_in_order():
    camera = FakeCamera(frames=[b"a", b"b"])

    assert [camera.capture() for _ in range(3)] == [b"a", b"b", b"a"]


def test_fake_camera_satisfies_camera_interface():
    assert isinstance(FakeCamera(), Camera)
