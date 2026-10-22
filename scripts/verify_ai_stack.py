import sys

print("Testing torch...", flush=True)
import torch
print(f"PyTorch version: {torch.__version__}, CUDA: {torch.cuda.is_available()}", flush=True)

print("Testing torchvision...", flush=True)
import torchvision
print(f"Torchvision version: {torchvision.__version__}", flush=True)

print("Testing ultralytics...", flush=True)
import ultralytics
print(f"Ultralytics version: {ultralytics.__version__}", flush=True)

print("Testing onnxruntime...", flush=True)
import onnxruntime
print(f"ONNX Runtime: {onnxruntime.__version__}, Providers: {onnxruntime.get_available_providers()}", flush=True)

print("Testing insightface...", flush=True)
import insightface
print(f"InsightFace version: {insightface.__version__}", flush=True)

print("ALL AI STACK IMPORTS SUCCESSFUL!", flush=True)
