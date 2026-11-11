from hardware.fake_motor import FakeMotor, MotorAction
from hardware.motor import Motor


def test_fake_motor_records_actions_in_order():
    motor = FakeMotor()

    motor.rotate(90)
    motor.rotate(-45.5)
    motor.stop()

    assert motor.actions == [
        MotorAction(name="rotate", degrees=90),
        MotorAction(name="rotate", degrees=-45.5),
        MotorAction(name="stop"),
    ]


def test_fake_motor_does_not_raise_hardware_errors():
    motor = FakeMotor()

    motor.rotate(360)
    motor.stop()
    motor.stop()


def test_fake_motor_satisfies_motor_interface():
    assert isinstance(FakeMotor(), Motor)
