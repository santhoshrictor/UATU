import os
import sys
from insightface.app import FaceAnalysis

# Define our local models directory
target_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models', 'insightface'))
os.makedirs(target_dir, exist_ok=True)

print(f"Triggering auto-download of buffalo_l models to: {target_dir}", flush=True)

# Initializing FaceAnalysis with a specific root forces it to download the .onnx files there if missing
app = FaceAnalysis(name='buffalo_l', root=target_dir)
try:
    app.prepare(ctx_id=0, det_size=(640, 640))
except Exception as e:
    print(f"CUDA initialization in prepare() yielded {e}, attempting CPU fallback (ctx_id=-1)...", flush=True)
    app.prepare(ctx_id=-1, det_size=(640, 640))

print("Download and extraction complete. The .onnx files are ready.", flush=True)
