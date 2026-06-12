"""Computer-vision pipeline: detection, OCR, minimap parsing, map metadata.

This package is import-safe without the heavy ML dependencies (ultralytics,
easyocr). Those are imported lazily inside the backends that need them, so the
analysis layer and tests run on a minimal install.
"""
