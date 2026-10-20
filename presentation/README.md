# QuizMaster — Project Presentation

`../QuizMaster_Presentation.pptx` is an 11-slide widescreen (16:9) deck for
presenting the QuizMaster project:

| # | Slide | Covers |
|---|-------|--------|
| 1 | Cover — "Quizzes that grade instantly and keep improving" | Project intro, key stats |
| 2 | Assessment today is slow, manual & blind | Problem statement + baseline vs. QuizMaster |
| 3 | Built around 20 measurable quality goals | Quality objectives (Q01–Q20) + SRS snapshot |
| 4 | Two portals, one platform | Scope & user roles |
| 5 | Seven modules. One seamless system. | Modules & features, tech stack |
| 6 | Clean, modular architecture | System/database design, folder architecture |
| 7 | From sign-up to insight in six steps | Main system workflow + live screens |
| 8 | Full CRUD, fully integrated | CRUD operations & database integration |
| 9 | A dashboard that coaches every student | Working application (student side) |
| 10 | Quality isn't a chapter — it's built in | TQM workspace (Pareto, FMEA, PDCA…) |
| 11 | Results that speak for themselves | Outcomes, testing, roadmap, thank-you |

Design notes:

- Deep-navy creative backgrounds in the QuizMaster brand gradient
  (indigo → violet → cyan), generated with Pillow.
- Real screenshots from `docs/screenshots/`, placed uncropped-in-spirit
  inside browser/phone frames — each pre-cropped to its frame's exact
  aspect ratio, so nothing is ever stretched.
- **Manual advance**: slides move on click/keypress only (no auto-play),
  with smooth slide transitions and gentle staggered fade-in animations
  as each slide appears.
- **Presenter notes on every slide** (PowerPoint: View → Notes, or use
  Presenter View) — a ready-made talk track for each point.

## Regenerating

```bash
pip install python-pptx Pillow
python presentation/prep_assets.py   # backgrounds, logo, cropped screenshots
python presentation/build_deck.py    # writes ../QuizMaster_Presentation.pptx
```

Edit copy/design in `build_deck.py`; the design system (gradients,
shadows, transitions, animations, frames) lives in `deck_helpers.py`.
