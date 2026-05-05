# Chair Rendering Quality Contract (Iteration 2)

This document formalizes the acceptance rules used by the Figma plugin and admin pipeline.

## 1) Slide Order

- Mandatory chair slides are rendered in strict template order (top-to-bottom in Figma page layout).
- UI must not rely on JSON key order only; runtime order is resolved from frame coordinates.

Expected mandatory sequence:
1. `preview`
2. `dimensions`
3. `upholstery_material`
4. `seating_ergonomics`
5. `legs_material`
6. `color_palette`

## 2) Photo Source Contract

Input source is one product folder URL + variant filter. Photos are grouped as:
- `interior`
- `white_bg`
- `macro`

Selection policy for chairs:
- `preview`: interior first, fallback to neutral (`white_34` / `white_front`)
- `dimensions`: neutral first
- `upholstery_material`: macro first
- `seating_ergonomics`: neutral first
- `legs_material`: neutral first
- `color_palette`: 2nd interior if available, else 1st interior

## 3) Data Integrity Rules

- No cross-article / cross-variant mixing.
- All selected images for a job must come from the same folder + variant scope.
- Duplicate frames for the same job in `Pipeline Results` are cleaned before new render.

## 4) Stability Rules

- Per-slide timeout: 180 seconds.
- One automatic retry per failed slide.
- Job is considered complete only when all mandatory slides are uploaded.

## 5) Output Naming

Export naming contract:
- `<variant_id_or_article>_<index>_<slide_type>.png`
- Index is 1-based, in rendered order.

## 6) Checkpoint Checklist

- Correct order in output folder.
- Correct slide type image (no macro in preview).
- No foreign product in any slide.
- No duplicate slides.
- Mandatory set is complete.
