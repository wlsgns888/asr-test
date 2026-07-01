import sys
from dataclasses import dataclass

import pytest
from app.workers.pyannote_diarization_worker import select_diarization_device_name


@dataclass(frozen=True, slots=True)
class FakeDevice:
    type: str


@dataclass(frozen=True, slots=True)
class FakeCuda:
    available: bool

    def is_available(self) -> bool:
        return self.available


@dataclass(frozen=True, slots=True)
class FakeMps:
    available: bool

    def is_available(self) -> bool:
        return self.available


@dataclass(frozen=True, slots=True)
class FakeBackends:
    mps: FakeMps


@dataclass(frozen=True, slots=True)
class FakeTorch:
    cuda: FakeCuda
    backends: FakeBackends

    def device(self, name: str) -> FakeDevice:
        return FakeDevice(type=name)


def test_select_device_prefers_mps_when_auto_and_cuda_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: Apple Silicon MPS is available and no explicit override is set.
    fake_torch = FakeTorch(
        cuda=FakeCuda(available=False),
        backends=FakeBackends(mps=FakeMps(available=True)),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.delenv("DIARIZATION_DEVICE", raising=False)

    # When: the worker selects a device.
    device_name = select_diarization_device_name()

    # Then: MPS is selected for faster local diarization.
    assert device_name == "mps"


def test_select_device_respects_cpu_override(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: the user explicitly requests CPU execution.
    fake_torch = FakeTorch(
        cuda=FakeCuda(available=True),
        backends=FakeBackends(mps=FakeMps(available=True)),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setenv("DIARIZATION_DEVICE", "cpu")

    # When: the worker selects a device.
    device_name = select_diarization_device_name()

    # Then: no accelerator is used.
    assert device_name is None
