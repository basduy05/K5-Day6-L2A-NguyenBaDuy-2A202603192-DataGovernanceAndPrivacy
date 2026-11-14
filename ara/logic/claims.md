# Claims

## C01: Adaptive Camera Normalization Eliminates Cam_B False Alarms
- **Statement**: Normalizing Laplacian variance by camera_id prevents soft-lens cameras (cam_B) from being falsely prioritized in the review queue.
- **Status**: hypothesis
- **Provenance**: ai-suggested
- **Falsification criteria**: If Cam_B false alarm rate remains > 30% in top-B review queue.
- **Proof**: ["pending"]
- **Dependencies**: []
- **Tags**: triage, camera_conditioning, sharpness

## C02: Light-Conditioned Exposure Scoring Separates True Sensor Defects from Night Scenes
- **Statement**: Dampening dark-pixel penalties for night images while amplifying glare penalties increases Defect Recall@20 on eval set.
- **Status**: hypothesis
- **Provenance**: ai-suggested
- **Falsification criteria**: If night clean images are still ranked in top-20 review queue.
- **Proof**: ["pending"]
- **Dependencies**: [C01]
- **Tags**: exposure, glare, night_scenes
