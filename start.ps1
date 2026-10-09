tailscale serve --https=20012  --bg http://localhost:22212
adb connect 10.0.0.114:5555
. .venv\Scripts\activate.ps1
python gui.py --run alas --port 22212