# Heuristics

## H01: Central ROI Laplacian Variance for License Plate / Frontal Focus
- **Rationale**: Edge-of-frame blur is often acceptable in wide-angle lenses, but central ROI blur directly affects vehicle and plate identification.
- **Provenance**: ai-suggested
- **Sensitivity**: medium
- **Code ref**: ["src/pipeline.py:process"]

## H02: Block Boundary Discontinuity for JPEG Artifacts
- **Rationale**: 8x8 DCT grid edges display abnormal gradient jumps in heavily compressed frames.
- **Provenance**: ai-suggested
- **Sensitivity**: low
- **Code ref**: ["src/pipeline.py:_compute_jpeg_blockiness"]
