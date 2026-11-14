Baseline: `baseline` (git 83ce56d, seed 42) · PoC: `poc` (git 83ce56d, seed 42)

| Metric (unit) | Slice | Baseline | PoC | Δ abs | Δ rel | Better | N |
|---|---|---|---|---|---|---|---|
| **Defect Recall@B** (ratio) | all | 0.5000 | 0.9000 | 0.4000 | +80.0% | higher | 40 |
| Precision@B (ratio) | all | 0.5000 | 0.9000 | 0.4000 | +80.0% | higher | 40 |
| False alarm in top-B (ratio) | light=night | 0.7000 | 0.1000 | -0.6000 | -85.7% | lower | 10 |
| False alarm in top-B (ratio) | light=day | 0.3000 | 0.0500 | -0.2500 | -83.3% | lower | 20 |
| Runtime / 100 items (s) | all | 0.2514 | 0.5822 | | | lower | |
