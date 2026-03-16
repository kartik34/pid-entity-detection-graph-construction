# P&ID Audit Report

## Summary

- **Nodes extracted**: 79
- **Edges extracted**: 72
- **SOP equipment records**: 5
- **Findings**: 0 errors, 1 warnings, 4 info
- **Passes**: 4 SOP checks passed

## SOP Equipment Limits

| Equipment | Max Pressure (PSIG) | Temp Range (°F) |
|---|---|---|
| F-715 A and B Particulate Filters | 275 | 100.0 |
| V-745 Stabilizer Tower | 300 | 375.0 |
| E-742 Exchanger (Shell) | 300 | 375.0 |
| E-742 Exchanger (Tube) | 300 | 250.0 |
| AC-746 After Cooler | 350 | -20.0 to 400.0 |

## Warnings

**[E-742]** Temperature mismatch on E-742: SOP=250 to 250 F, P&ID=375 F.

- SOP: `250 to 250` | P&ID: `375`

## Passes

- `F-715` — F-715 (F-715 A and B Particulate Filters) passed: no SOP-vs-P&ID mismatches detected.
- `V-745` — V-745 (V-745 Stabilizer Tower) passed: no SOP-vs-P&ID mismatches detected.
- `E-742` — E-742 (E-742 Exchanger (Shell)) passed: no SOP-vs-P&ID mismatches detected.
- `AC-746` — AC-746 (AC-746 After Cooler) passed: no SOP-vs-P&ID mismatches detected.

---
