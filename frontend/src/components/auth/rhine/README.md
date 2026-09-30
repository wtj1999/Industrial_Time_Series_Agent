# RhineLabUI scene integration
Upstream: https://github.com/LBEILC/RhineLabUI
Commit: ee5779741c6c0c916e416705fa634c7abf905c73
License: MIT (see LICENSE).

The original scene, physical glass shader, lighting, shared-depth AO / bokeh, array coverage, critical damping, extraction and camera framing are retained. Local adaptations: time-window records, signal label, local GLB path, click-only interaction, no pointer parallax or manual camera controls. React owns lifecycle and authentication; the scene remains native Three.js.

The model reveal uses the upstream decryption phases and projected scan intervals, with a local overlay in ModelRevealOverlay.ts. Detail glass roughness and depth of field are calibrated for the precision signal inserts. Selecting another window restarts the reveal; reduced-motion mode clears it immediately.
