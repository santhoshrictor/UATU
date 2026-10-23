import os
from ultralytics import YOLO

target_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models', 'yolo11n-pose.pt'))
os.makedirs(os.path.dirname(target_path), exist_ok=True)
print(f"Downloading YOLO11n-Pose to {target_path}...")

model = YOLO(target_path)
print("Download complete. Pose model is secured locally.")
