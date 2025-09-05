import types


def test_compare_versions_basic():
    from app.utils import update_notifier as un

    assert un._compare_versions("1.2.3", "1.2.4") == -1
    assert un._compare_versions("v1.2.3", "1.2.3") == 0
    assert un._compare_versions("1.3.0", "1.2.9") == 1


def test_compare_versions_prerelease():
    from app.utils import update_notifier as un

    # packaging understands pre/post/dev comparisons
    assert un._compare_versions("1.2.3.post1", "1.2.3") == 1
    assert un._compare_versions("1.2.3.dev1", "1.2.3") == -1


def test_notify_disabled(monkeypatch):
    from app.utils import update_notifier as un

    class FakeLog:
        def __init__(self):
            self.infos = []
            self.warnings = []

        def info(self, msg):
            self.infos.append(str(msg))

        def warning(self, msg):
            self.warnings.append(str(msg))

    flog = FakeLog()
    monkeypatch.setenv("ANIBRIDGE_UPDATE_CHECK", "0")
    monkeypatch.setattr(un, "logger", flog)
    un.notify_on_startup()
    assert any("Update check disabled" in m for m in flog.infos)


def test_notify_up_to_date(monkeypatch):
    from app.utils import update_notifier as un

    class FakeLog:
        def __init__(self):
            self.infos = []
            self.warnings = []

        def info(self, msg):
            self.infos.append(str(msg))

        def warning(self, msg):
            self.warnings.append(str(msg))

    flog = FakeLog()
    monkeypatch.setenv("ANIBRIDGE_UPDATE_CHECK", "1")
    monkeypatch.setattr(un, "check_for_update", lambda: ("1.0.0", "1.0.0"))
    monkeypatch.setattr(un, "IN_DOCKER", False)
    monkeypatch.setattr(un, "logger", flog)
    un.notify_on_startup()
    assert any("current=1.0.0, latest=1.0.0" in m for m in flog.infos)
    assert any("up-to-date" in m for m in flog.infos)


def test_notify_update_available_host(monkeypatch):
    from app.utils import update_notifier as un

    class FakeLog:
        def __init__(self):
            self.infos = []
            self.warnings = []

        def info(self, msg):
            self.infos.append(str(msg))

        def warning(self, msg):
            self.warnings.append(str(msg))

    flog = FakeLog()
    monkeypatch.setenv("ANIBRIDGE_UPDATE_CHECK", "1")
    monkeypatch.setattr(un, "check_for_update", lambda: ("1.0.0", "1.1.0"))
    monkeypatch.setattr(un, "IN_DOCKER", False)
    monkeypatch.setattr(un, "logger", flog)
    un.notify_on_startup()
    assert any("current=1.0.0, latest=1.1.0" in m for m in flog.infos)
    assert any("Please update to v1.1.0" in m for m in flog.warnings)


def test_notify_update_available_docker(monkeypatch):
    from app.utils import update_notifier as un

    class FakeLog:
        def __init__(self):
            self.infos = []
            self.warnings = []

        def info(self, msg):
            self.infos.append(str(msg))

        def warning(self, msg):
            self.warnings.append(str(msg))

    flog = FakeLog()
    monkeypatch.setenv("ANIBRIDGE_UPDATE_CHECK", "1")
    monkeypatch.setattr(un, "check_for_update", lambda: ("1.0.0", "1.1.0"))
    monkeypatch.setattr(un, "IN_DOCKER", True)
    monkeypatch.setattr(un, "GHCR_IMAGE", "owner/image")
    monkeypatch.setattr(un, "logger", flog)
    un.notify_on_startup()
    assert any("current=1.0.0, latest=1.1.0" in m for m in flog.infos)
    assert any("ghcr.io/owner/image:v1.1.0" in m for m in flog.warnings)
