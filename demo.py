"""One-command demo: starts the API and the sensor simulator, stops both on Ctrl+C.

    python demo.py              # opens the dashboard in your browser
    python demo.py --no-browser
"""
import os
import subprocess  # nosec B404
import sys
import time
import urllib.request
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    port = os.environ.get("PORT", "5000")
    url = f"http://127.0.0.1:{port}"
    api = subprocess.Popen([sys.executable, "app.py"], cwd=HERE)  # nosec B603
    for _ in range(40):  # wait until the API answers
        try:
            urllib.request.urlopen(f"{url}/api/health", timeout=1)  # nosec B310
            break
        except OSError:
            time.sleep(0.25)
    else:
        print("The server did not start. Is port " + port + " already in use? Close the other window, or set PORT to another number.")
        api.terminate()
        return 1
    sim = subprocess.Popen([sys.executable, "simulator.py"], env={**os.environ, "API": url}, cwd=HERE)  # nosec B603
    print(f"\nWard Zero is running at {url}")
    print("Press the highlighted button on the page to walk through the demo. Ctrl+C here to stop.\n")
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    try:
        while api.poll() is None and sim.poll() is None:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for p in (sim, api):
            p.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
