# Meeting Minutes ASR Design System

## Product Posture

The app is an operational meeting-minutes workbench. It should feel calm,
fast, and repeatable: users arrive with an audio file, run the pipeline, and
leave with saved minutes. Avoid marketing composition, decorative imagery, and
large hero treatments.

## Layout

- Use one full-width application surface with constrained inner content.
- Keep the primary workflow visible above the fold on desktop.
- Place upload, processing status, capability status, and results in separate
  un-nested panels.
- Repeated workflow steps may use compact cards with an 8px radius.

## Tokens

- Surface: `#f7f8fa`
- Panel: `#ffffff`
- Border: `#d8dee8`
- Text: `#17202e`
- Muted text: `#607086`
- Accent: `#2563eb`
- Accent strong: `#1d4ed8`
- Success: `#0f8a5f`
- Warning: `#b45309`
- Error: `#b42318`
- Radius: `8px`
- Shadow: `0 12px 30px rgba(23, 32, 46, 0.08)`

## Components

- Buttons use clear command labels and stable heights.
- File inputs, text areas, and result panes use visible focus outlines.
- Status steps use fixed layout dimensions so labels do not shift while the
  pipeline runs.
- Korean text must not be clipped on mobile; keep line-height at or above 1.45.

## Capability Disclosure

Speaker separation is available when `pyannote/speaker-diarization-community-1`
is configured with a Hugging Face token. The UI must show whether the local
runtime is configured and must keep users informed during long ASR, diarization,
and forced-alignment work.
