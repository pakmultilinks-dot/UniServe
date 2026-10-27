"""Verify fresh presentation identities on an immutable APK without placing orders."""
from pathlib import Path

# Reuse reviewed transport and emulator helpers without running order fixtures.
helpers = Path("scripts/android_native_smoke.py").read_text().partition("\ntry:\n")[0]
exec(compile(helpers, "scripts/android_native_smoke.py", "exec"))

try:
    backend_ready()
    adb("install", "-r", "native-apk/app-release.apk")
    config = json.loads(Path("apps/mobile/app.json").read_text())["expo"]
    package_info = adb("shell", "dumpsys", "package", PACKAGE)
    assert "versionName=" + config["version"] in package_info
    component = adb("shell", "cmd", "package", "resolve-activity", "--brief", PACKAGE).strip().splitlines()[-1]
    for role in ("student", "faculty"):
        # Only this workflow's disposable emulator is reset.
        adb("shell", "am", "force-stop", PACKAGE)
        adb("shell", "pm", "clear", PACKAGE)
        adb("shell", "am", "start", "-W", "-n", component)
        root = wait_text("Get Started", 90)
        entries = labelled_nodes(root, "Log in")
        assert entries, "Welcome login action missing"
        tap(entries[0]); root = wait_text("Welcome Back", 45)
        fields = [n for n in root.iter("node") if n.attrib.get("class") == "android.widget.EditText"]
        tap(fields[0]); type_text(ACCOUNTS[role]["email"])
        _, root = dump()
        fields = [n for n in root.iter("node") if n.attrib.get("class") == "android.widget.EditText"]
        tap(fields[1]); type_text(ACCOUNTS[role]["password"])
        adb("shell", "input", "keyevent", "4")
        _, root = dump(); tap(labelled_nodes(root, "Log In")[0])
        wait_text("Current cafeteria:", 160)
        snap("presentation-" + role + "-home")
        link("orders"); root = wait_text("Orders", 45)
        snap("presentation-" + role + "-clean-orders")
        link("profile"); wait_text(ACCOUNTS[role]["email"], 45)
        snap("presentation-" + role + "-profile")
        token = login_api(role)
        assert api("GET", "/orders/?days=90", token)["orders"] == [], "Presentation history must remain clean"
        api("POST", "/auth/logout-all", token)
        print("PASS fresh presentation native login/profile/empty order history:", role, flush=True)
finally:
    (OUT / "crash-log.txt").write_text(adb("logcat", "-b", "crash", "-d"))
