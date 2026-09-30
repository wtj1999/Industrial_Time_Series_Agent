# Precision time-series cassette

The active asset is `time-series-precision-v2.glb`, authored and exported through Blender MCP in Blender 5.2.2 LTS. Editable source: `../../art/time-series-precision-v2.blend`; insert generator: `../../art/build_precision_v2.py` (run with the original cassette scene active).

Three bevelled metallic signal ribbons sit above recessed ceramic beds with support pedestals, double guide rails, etched time divisions, terminal contacts and fasteners. All time windows share this geometry; the upper-left time label identifies the selected window. Per-window measurements remain in the separate UI chart. No mesh decimation was applied.

The precise enclosure, layered cover, engraving, fasteners and substrate originate from LBEILC/RhineLabUI, commit ee5779741c6c0c916e416705fa634c7abf905c73, art/archive-assembly.blend. MIT license retained in RhineLabUI-LICENSE.txt.

The previous `time-series-cassette.glb`, its Blender source and generator are retained for rollback. The original warm frontend palette is saved under `../../art/palettes/warm-original`.

## Current login presentation
The login scene uses the original optical enclosure from this asset, excluding all `precision__` mechanical insert meshes. Its three channels are now drawn as a high-resolution transparent signal print (`src/components/auth/rhine/signal-print.ts`), with fine blue curves and subtle area washes. The print follows the glass scan clarity and remains identical between archive windows. V2 geometry remains in the source asset for rollback.
