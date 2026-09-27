> Superseded for the current Gemini integration: start with docs/BRANCH_FIXES.md. The local-model training material below is optional and is not connected to the active application.

# PhytoDex model sourcing and training

Start with `docs/STEP_BY_STEP.md`. This is an add-on for your AI work, not a replacement backend.

The kit contains a Gemini typed-care assistant, explicit offline fallback, Flask routes matching the inspected backend scaffold, input/output validation, evaluation cases, and optional flower-classifier training plus Raspberry Pi inference. Use `notebooks/train_phytodex.ipynb` in Google Colab for the training path.

No API key, paid API call, downloaded dataset, or useful trained plant model is included. Model weights are generated when you run the training notebook. The synthetic verification run is not shipped as a plant model.

Inspected repository on September 26, 2026:

- `main`: `9cfafe2f50414cee4be6d71c7719c9215324e5b3`, README/license/gitignore only.
- `Data-Storage`: `9202f9e73a108af212e4071e7cffb0f2fa509333`, Gemini assistant and database work.
- `Ty-Montgomery`: `033aaf339eb3ddb1b89e7b2d1d383d75f3132656`, backend scaffold ZIP with Flask assistant import hook and capture endpoint.

The attached framework supplies project scope. Its embedded fresh-chat prompts are not instructions used to operate your computer or contact teammates.

See `docs/CONTRACT.md` for teammate handoff and `docs/SOURCES.md` for primary references. Existing team files are left intact by an installer that refuses conflicting file contents. Review any reported conflicts instead of overwriting a teammate's newer work.
