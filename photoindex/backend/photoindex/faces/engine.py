"""Face detection (SCRFD) and recognition (ArcFace) from InsightFace's buffalo_l models, run with onnxruntime.

We use the two .onnx files directly rather than the insightface package, which has no Python 3.13 builds.
The models are licensed for non-commercial use (personal libraries are fine).
"""

import hashlib
import io
import logging
import threading
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

log = logging.getLogger(__name__)

MODELS_URL = "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip"
MODELS = {  # file in the zip -> sha256
    "det_10g.onnx": "5838f7fe053675b1c7a08b633df49e7af5495cee0493c7dcf6697200b85b5b91",
    "w600k_r50.onnx": "4c06341c33c2ca1f86781dab0e829f88ad5b64be9fba56e56bc9ebdefc619e43",
}
DET_SIZE = 640
STRIDES = (8, 16, 32)
ANCHORS_PER_CELL = 2
# Where ArcFace expects the eyes, nose and mouth corners in its 112x112 input.
ARCFACE_DST = np.array([[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366],
                        [41.5493, 92.3655], [70.7299, 92.2041]], dtype=np.float32)


@dataclass
class DetectedFace:
    box: tuple[float, float, float, float]  # x, y, w, h in pixels of the input image
    score: float
    landmarks: np.ndarray  # 5x2: eyes, nose, mouth corners
    embedding: np.ndarray  # 512 floats, L2-normalised
    sharpness: float  # variance of the Laplacian of the aligned face


def ensure_models(models_dir: Path) -> None:
    """Download and verify the two model files if they aren't there yet."""
    if all((models_dir / name).exists() for name in MODELS):
        return
    models_dir.mkdir(parents=True, exist_ok=True)
    log.info("downloading face models from %s", MODELS_URL)
    with urllib.request.urlopen(MODELS_URL, timeout=600) as r:
        archive = zipfile.ZipFile(io.BytesIO(r.read()))
    for name, digest in MODELS.items():
        data = archive.read(name)
        if hashlib.sha256(data).hexdigest() != digest:
            raise RuntimeError(f"{name}: checksum mismatch, refusing to use it")
        (models_dir / name).write_bytes(data)


def _session(path: Path) -> ort.InferenceSession:
    opts = ort.SessionOptions()
    opts.log_severity_level = 3
    return ort.InferenceSession(str(path), opts, providers=["CPUExecutionProvider"])


def _nms(boxes: np.ndarray, scores: np.ndarray, thresh: float = 0.4) -> list[int]:
    x1, y1, x2, y2 = boxes.T
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size:
        i = order[0]
        keep.append(int(i))
        xx1, yy1 = np.maximum(x1[i], x1[order[1:]]), np.maximum(y1[i], y1[order[1:]])
        xx2, yy2 = np.minimum(x2[i], x2[order[1:]]), np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0, xx2 - xx1 + 1) * np.maximum(0, yy2 - yy1 + 1)
        order = order[1:][inter / (areas[i] + areas[order[1:]] - inter) <= thresh]
    return keep


class FaceEngine:
    def __init__(self, models_dir: Path):
        ensure_models(models_dir)
        self.det = _session(models_dir / "det_10g.onnx")
        self.rec = _session(models_dir / "w600k_r50.onnx")
        self._det_input = self.det.get_inputs()[0].name
        self._rec_input = self.rec.get_inputs()[0].name
        self._centers = {}
        for s in STRIDES:
            n = DET_SIZE // s
            grid = np.stack(np.mgrid[:n, :n][::-1], axis=-1).astype(np.float32).reshape(-1, 2) * s
            self._centers[s] = np.repeat(grid, ANCHORS_PER_CELL, axis=0)

    def detect(self, rgb: np.ndarray, min_score: float = 0.5) -> list[DetectedFace]:
        h, w = rgb.shape[:2]
        scale = DET_SIZE / max(h, w)
        nh, nw = int(round(h * scale)), int(round(w * scale))
        canvas = np.zeros((DET_SIZE, DET_SIZE, 3), dtype=np.float32)
        canvas[:nh, :nw] = cv2.resize(rgb, (nw, nh))
        blob = ((canvas - 127.5) / 128.0).transpose(2, 0, 1)[None]
        outs = [o[0] if o.ndim == 3 else o for o in self.det.run(None, {self._det_input: blob})]

        boxes, scores, kpss = [], [], []
        n = len(STRIDES)
        for i, s in enumerate(STRIDES):
            sc = outs[i].reshape(-1)
            pos = np.where(sc >= min_score)[0]
            if not pos.size:
                continue
            c = self._centers[s][pos]
            d = outs[i + n][pos] * s
            k = outs[i + 2 * n][pos] * s
            boxes.append(np.stack([c[:, 0] - d[:, 0], c[:, 1] - d[:, 1], c[:, 0] + d[:, 2], c[:, 1] + d[:, 3]], 1))
            kpss.append(np.stack([c[:, 0:1] + k[:, 0::2], c[:, 1:2] + k[:, 1::2]], -1))
            scores.append(sc[pos])
        if not boxes:
            return []
        boxes_a, scores_a, kps_a = np.concatenate(boxes) / scale, np.concatenate(scores), np.concatenate(kpss) / scale
        faces = []
        for i in _nms(boxes_a, scores_a):
            x1, y1, x2, y2 = boxes_a[i]
            x1, y1, x2, y2 = max(0.0, x1), max(0.0, y1), min(float(w), x2), min(float(h), y2)
            aligned = self._align(rgb, kps_a[i])
            faces.append(DetectedFace(
                box=(float(x1), float(y1), float(x2 - x1), float(y2 - y1)), score=float(scores_a[i]),
                landmarks=kps_a[i], embedding=self._embed(aligned),
                sharpness=float(cv2.Laplacian(cv2.cvtColor(aligned, cv2.COLOR_RGB2GRAY), cv2.CV_64F).var()),
            ))
        return faces

    def _align(self, rgb: np.ndarray, kps: np.ndarray) -> np.ndarray:
        m, _ = cv2.estimateAffinePartial2D(kps.astype(np.float32), ARCFACE_DST, method=cv2.LMEDS)
        return cv2.warpAffine(rgb, m, (112, 112), borderValue=0)

    def _embed(self, aligned: np.ndarray) -> np.ndarray:
        blob = ((aligned.astype(np.float32) - 127.5) / 127.5).transpose(2, 0, 1)[None]
        v = self.rec.run(None, {self._rec_input: blob})[0][0]
        return v / np.linalg.norm(v)


_engine: FaceEngine | None = None
_engine_lock = threading.Lock()


def get_engine() -> FaceEngine:
    global _engine
    with _engine_lock:
        if _engine is None:
            from photoindex.config import get_settings

            _engine = FaceEngine(Path(get_settings().models_dir).expanduser())
        return _engine
