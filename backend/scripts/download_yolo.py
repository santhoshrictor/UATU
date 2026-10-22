import os
from ultralytics import YOLO

target_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "yolo11n.pt"))
os.makedirs(os.path.dirname(target_path), exist_ok=True)
print(f"Downloading YOLO11n to {target_path}...")

# Initializing with the absolute path forces Ultralytics to download it there
model = YOLO(target_path)
print("Download complete. YOLO11n is ready.")
