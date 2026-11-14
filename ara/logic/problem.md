# Problem

## Raw QC Triage (T02)
- **Domain**: Automotive perception and data curation.
- **Bottleneck**: Manual inspection of raw data streams is cost-prohibitive. Reviewers can only inspect B=20 candidate frames out of 96 frames.
- **Core Challenge**: Maximizing Defect Recall@B while keeping False Alarm low across disparate camera optics (cam_A, cam_B) and lighting conditions (day, dusk, night).
- **Constraints**: 100% offline execution, seed 42 reproducibility, provenance verification, strict separation from hidden ground truth.
