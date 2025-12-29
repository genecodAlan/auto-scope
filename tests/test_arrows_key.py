import threading
import pytest
from micro_camera_scope.Arrows_Key import MicroscopeStitcher


class FakeArduino:
    def __init__(self, fail_write=False):
        self.written = []
        self.fail_write = fail_write

    def write(self, data):
        if self.fail_write:
            raise Exception("fake write error")
        self.written.append(data)


def test_send_step_updates_position_on_success(monkeypatch):
    app = MicroscopeStitcher(create_gui=False)
    app.arduino = FakeArduino()
    app.arduino_connected = True

    app.abs_x = 0
    app.abs_y = 0

    ok = app.send_step('U', 'S')
    assert ok is True
    assert app.abs_y == 1


def test_send_step_blocks_negative_when_home_set(monkeypatch):
    app = MicroscopeStitcher(create_gui=False)
    app.arduino = FakeArduino()
    app.arduino_connected = True

    app.set = True
    app.abs_x = 0
    app.abs_y = 0

    ok = app.send_step('D', 'S')
    assert ok is False
    assert app.abs_y == 0
    assert "Exceeded Limit Boundaries" in app.status_var.get()


def test_send_step_rollback_on_comm_error(monkeypatch):
    app = MicroscopeStitcher(create_gui=False)
    app.arduino = FakeArduino(fail_write=True)
    app.arduino_connected = True

    app.abs_x = 0
    app.abs_y = 0

    ok = app.send_step('U', 'S')
    assert ok is False
    assert app.abs_y == 0
    assert "COMMUNICATION ERROR" in app.status_var.get()


def test_start_auto_scan_warns_if_not_at_origin(monkeypatch):
    app = MicroscopeStitcher(create_gui=False)
    app.arduino_connected = True
    app.set = True
    app.abs_x = 2
    app.abs_y = 1

    monkeypatch.setattr('tkinter.messagebox.askyesno', lambda *a, **k: False)

    app.start_auto_scan()
    assert app.auto_scan_active is False
    assert "cancelled" in app.status_var.get().lower()


def test_stop_stitching_stops_auto_scan_and_sends_stop():
    app = MicroscopeStitcher(create_gui=False)
    fake = FakeArduino()
    app.arduino = fake
    app.arduino_connected = True
    app.auto_scan_active = True

    # Dummy thread object with join
    class DummyThread:
        def join(self, timeout=None):
            return

    app.lawnmower_thread = DummyThread()

    app.stop_stitching()

    assert app.auto_scan_active is False
    # Check that SS stop command was sent
    assert any(b'SS' in w for w in fake.written)