from dataclasses import dataclass, field


@dataclass(frozen=True)
class MotorAction:
    name: str
    degrees: float | None = None


@dataclass
class FakeMotor:
    """不需硬體的馬達。只記錄動作供測試檢查，不拋出硬體錯誤。"""

    actions: list[MotorAction] = field(default_factory=list)

    def rotate(self, degrees: float) -> None:
        self.actions.append(MotorAction(name="rotate", degrees=degrees))

    def stop(self) -> None:
        self.actions.append(MotorAction(name="stop"))
