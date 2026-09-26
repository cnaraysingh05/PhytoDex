# Your PhytoDex AI work step by step

Your first deliverable is a reliable typed plant-care assistant on the Pi. Source an existing Gemini model for that. Your optional second deliverable is a small image classifier trained in Colab and run locally on the Pi. The two models solve different problems and must not be presented as interchangeable.

The framework prioritizes typed guidance and makes camera identification a stretch goal. Since your message did not specify which model you meant, this kit covers both. Complete steps 1–8 first; do steps 9–13 if photos/training are part of your agreed scope. You do not need to reflash the Pi or repeat SSH setup.

## 1 Understand what you are sourcing

The existing `Data-Storage/assistant.py` uses Gemini and the fields `likely_causes`, `what_to_check`, `recommended_actions`, `urgency`, `uncertainty_note`, and `source`. This kit preserves those fields and the function `get_plant_guidance(species, message)`.

Gemini is accessed over the internet: the Pi hosts the service but Google's servers run the language model. No custom language-model training is necessary for this MVP. You do not yet have a reviewed training dataset that would justify fine-tuning. Prompting, schema validation, and evaluation are the useful work now.

The optional photo path starts with MobileNetV2 ImageNet weights and trains a new classifier head. This is actual transfer learning. TensorFlow's flower dataset has 3,670 images in five categories: daisy, dandelion, roses, sunflowers, tulips. It is a training demonstration with a limited vocabulary, not a pothos/monstera identifier or disease detector. PlantVillage's crop disease task would also be a different target from general houseplant identification.

## 2 Put your AI files into your Mac checkout

Open a new Mac Terminal window. Keep your SSH window separate so commands go to the intended computer. In a fresh location, run:

```bash
mkdir -p ~/Documents/PhytoDex-work
cd ~/Documents/PhytoDex-work
git clone https://github.com/cnaraysingh05/PhytoDex.git
cd PhytoDex
git switch -c feature/model-sourcing
```

If you already have a checkout, open that folder instead of cloning again. Run `git status` first; preserve any existing work. If this branch already exists, use `git switch feature/model-sourcing`. Do not reset your branch to match this guide.

The kit is already available at the following path on your Mac. From the repository folder run this exact command:

```bash
python3 /Users/chrisnaraysingh/Documents/Codex/2026-09-26/okay-we-are-now-working-on/outputs/phytodex-ai-kit/install_into_repo.py "$PWD"
```

Why: this adds only AI-owned files and generated-file ignore rules. It does not replace the README, database, main app, or frontend. It stops before copying if any existing AI files differ. Resolve those with the file owner; do not force an overwrite. The root `assistant.py` on Data-Storage is not the file imported by the scaffold: the deployed implementation lives at `backend/services/assistant.py`.

## 3 Install the small assistant dependencies

On the Mac, in the repo:

```bash
python3 -m venv .venv-ai
source .venv-ai/bin/activate
python -m pip install -r requirements-ai.txt
python -m unittest discover -s tests_ai -p 'test_assistant.py' -v
AI_MODE=offline python scripts/check_ai.py
```

Use Python 3.11–3.13 for this kit; the assistant was checked with Python 3.13.7. The offline check should return JSON with `source: "fallback"` and `fallback_reason: "offline_mode"`. This is success for the offline test, not evidence that Gemini is connected.

Why: a virtual environment keeps project packages separate, and the first test proves the route can work when Wi-Fi, a key, or cloud access is unavailable. The fallback is a general authored checklist; it does not pretend to diagnose the plant.

## 4 Connect the pretrained assistant model

Open https://aistudio.google.com/apikey and create/select an API key in your own project. Keep the key private. Do not paste it into this chat, code, GitHub, or a frontend setting. Check the project's quota/billing settings before running live evaluations.

In your Mac repo terminal:

```bash
python scripts/configure_ai.py
python scripts/check_ai.py
```

The configuration script asks for the key with hidden input and writes a private `.env.ai`. It suggests `gemini-3.8-flash`, documented by Google at the time of inspection. Choose a model available in your project. If your team already has working access to `gemini-2.5-flash`, you can enter that model name instead. Google's September 22 documentation says 2.5 access is restricted to prior active users, so do not assume a new key can use the branch's old default.

Success: `source` is `gemini`, `model` is your selected model, and `fallback_reason` is null. If it falls back, the command exits with an error. Check AI Studio model access, quota, key restrictions and connectivity. The service deliberately does not return provider error text or secrets to browsers. To update configuration later, edit `.env.ai` locally and restart the process. The script refuses to overwrite an existing file. Shell environment variables take precedence over the dotenv file.

Why: you are sourcing model access and verifying a real response, not merely importing an SDK. A successful HTTP response containing a fallback is not a successful cloud test.

## 5 Test the endpoint before frontend integration

Start the standalone service on the Mac:

```bash
python run_ai.py
```

In a second Mac terminal:

```bash
curl -s http://127.0.0.1:5001/api/ai/health
curl -s http://127.0.0.1:5001/api/assistant \
  -H 'Content-Type: application/json' \
  -d '{"species":"Pothos","message":"Leaves are yellow and the soil has stayed wet for a week."}'
```

This test service uses port 5001 to avoid taking the team's usual backend port. It has no PlantDex, Garden, or frontend page. Stop it with Control+C when done.

Why: this isolates the AI endpoint so your teammate can integrate a known request/response contract. It runs with Waitress, without Flask's debug mode.

## 6 Evaluate the assistant before calling it done

In your activated environment:

```bash
python scripts/evaluate_assistant.py --live
```

This makes six live requests and writes `ml-runs/assistant-evaluation.json`. Read every case. The file includes the expectation for each answer. Check wet-soil symptoms, dry-soil symptoms, missing species, negation, unknown-plant edibility, and an off-topic instruction. A valid JSON schema does not prove good care advice. Reject confident diagnoses with insufficient context, invented facts, or contradictory watering advice.

Then deliberately test offline mode:

```bash
AI_MODE=offline python scripts/check_ai.py
```

Why: you need evidence for both the normal and failure paths. Tell the frontend owner to visibly label `source: fallback` as “Offline care checklist.” Do not display its low urgency value as an assessed urgency; the uncertainty note explains that urgency has not been assessed.

## 7 Commit your files and hand off the contract

From the Mac repo:

```bash
git status --short
git check-ignore .env.ai
git add .gitignore .env.ai.example README_AI.md requirements-ai.txt requirements-vision.txt run_ai.py
git add backend/routes/assistant.py backend/services/assistant.py
git add backend/routes/identify.py backend/services/vision.py
git add scripts ml notebooks tests_ai docs
git diff --cached --stat
git diff --cached --name-only
git commit -m "feat: add plant assistant and optional vision training pipeline"
git push -u origin feature/model-sourcing
```

Inspect the staged filenames before committing: no `.env.ai`, raw dataset, generated model, environment, or evaluation output should be present. GitHub may ask you to authenticate. Do not put a token in the repository URL.

Open your repository on GitHub, use Compare & pull request, and target `main`. Share `docs/CONTRACT.md` with the backend/frontend owners yourself. Once the backend scaffold is extracted into their branch, its `app.py` already imports `backend.routes.assistant.assistant_bp`; this kit fits that hook. The new `/api/identify` route needs the optional registration described in step 12. Do not start the old root assistant as a separate competing implementation.

When the scaffold is present, run `python scripts/integrate_ai_dependencies.py` and review `git diff -- requirements.txt` with the backend owner. This moves its old Flask 3.0.3 pin to this kit's Flask 3.1.3-or-newer constraint, needed for per-request upload limits, and includes the AI dependencies. Then install `python -m pip install -r requirements.txt`. Commit that reviewed dependency change separately.

Why: your teammate can review a small, distinct surface area. The current main branch has no running backend; these files do not magically integrate code still sitting inside another branch's ZIP.

## 8 Run your assistant on the Pi

In your SSH terminal, use the checkout you already cloned. If none exists, clone it once first:

```bash
cd ~
git clone https://github.com/cnaraysingh05/PhytoDex.git
```

Then, in the Pi checkout, provided it has no uncommitted teammate work:

```bash
cd ~/PhytoDex
git fetch origin
git switch feature/model-sourcing
git pull --ff-only
python3 -m venv .venv-ai
source .venv-ai/bin/activate
python -m pip install -r requirements-ai.txt
python scripts/configure_ai.py
python scripts/check_ai.py
python run_ai.py --host 0.0.0.0 --port 5001
```

Enter the key privately on the Pi as well; `.env.ai` was correctly excluded from Git. If the Pi checkout is shared and dirty, do not switch it: make a separate `~/PhytoDex-ai-test` clone with `git clone --branch feature/model-sourcing https://github.com/cnaraysingh05/PhytoDex.git ~/PhytoDex-ai-test` and run the same setup there.

From the Mac on the same private network:

```bash
curl -s http://phytodex.local:5001/api/assistant \
  -H 'Content-Type: application/json' \
  -d '{"species":"Pothos","message":"Leaves are yellow and soil stays wet."}'
```

If `.local` fails, replace it with the Pi's current IP address. After review/merge into the actual backend, install these dependencies into the environment used by that backend and use the team's app URL/port. The frontend should call its own backend at `/api/assistant`, not a hard-coded Mac URL. The hardware owner can then add the service to their existing startup arrangement.

Why: this proves the Pi hosts your endpoint. The live assistant still needs internet. Offline mode works locally. Keep the unauthenticated demo API on the team's private network; public deployment would need access and quota controls.

## 9 Optional train the image model in Colab

Use the supplied `notebooks/train_phytodex.ipynb`; you do not need to write a training script. Open https://colab.research.google.com, select File → Upload notebook, and choose that notebook from the kit. Select Runtime → Change runtime type → T4 GPU if available.

Run the notebook cells in order:

1. Upload the supplied `phytodex-ai-kit.zip` when prompted.
2. Install the training requirements.
3. Download the official flower images and create fixed splits.
4. Train the classifier head for up to eight epochs and export it.
5. Inspect validation/test metrics.
6. Download `phytodex-training-results.zip` before closing Colab.

There is no API key in this notebook. Training speed depends on assigned hardware; no fixed finish time is promised. A fresh runtime is easiest for a rerun. Scripts refuse to overwrite an existing split/model directory; for local repeated experiments, use a new `--out` path.

Equivalent local commands, in a separate Python 3.11–3.13 environment, are:

```bash
python -m pip install -r ml/requirements-train.txt
python ml/prepare_data.py
python ml/train.py --epochs 8
```

Why each training stage matters:

- **Source:** reuse ImageNet visual features so your small dataset does not have to teach the network basic shapes from zero.
- **Split before training:** train learns weights, validation chooses training settings/threshold, test measures the frozen final choice.
- **Deduplicate and group:** identical decoded images are removed; custom specimen groups stay in one split. Flower photos still lack reliable specimen identities, so dataset scores have that limitation.
- **Freeze the backbone:** initially train only the new classifier head. This is faster and reduces overfitting.
- **Optional fine-tuning:** `--fine-tune-epochs 3 --out models/flowers-v2` unfreezes the last layers at a smaller learning rate and keeps BatchNorm fixed. It restores the head-only model if validation loss worsens. Leave this off for your first run.
- **Export:** float16 stored weights reduce file size while keeping a simple float32 RGB input. The Pi runs the small inference runtime, not training.
- **Parity check:** compare Keras and exported predictions so a conversion/preprocessing mistake cannot silently pass.

## 10 Read the results honestly

The results ZIP contains `flowers/model.tflite`, `metadata.json`, `labels.json`, `metrics.json`, plus training artifacts and available attribution. Always copy model and metadata from the same run. The metadata records a SHA-256 hash and the exact class order.

In `metrics.json`, inspect test accuracy, macro F1 and per-class recall/support. The confusion matrix rows are true labels and columns are predicted labels. Check whether the system confuses specific classes rather than relying only on a headline accuracy.

The acceptance threshold is selected on validation data only, targeting at least 90% correctness among accepted examples with at least 20 accepted validation examples. This is a heuristic, not a statistical guarantee or an unknown-plant detector. If no threshold qualifies, it is set to 1.01 and all predictions are uncertain. Do not tune against your test set or lower the threshold to force a convincing demo.

Try at least ten new photos per supported category with the actual capture device and lighting, plus photos of unsupported plants and non-plants. Record how often the correct category appears, incorrect candidates, uncertainty, and Pi latency. High scores on unfamiliar objects can still be wrong. Flower categories are not exact scientific species identifications.

Why: held-out web photos do not measure the real cyberdeck experience. Do not claim a measured plant accuracy until you have run real training and reviewed these results.

## 11 Deploy only the runtime bundle to the Pi

After Colab downloads the ZIP to the Mac's Downloads folder, in the Mac repo:

```bash
mkdir -p models
unzip ~/Downloads/phytodex-training-results.zip -d models
ssh phytodex@phytodex.local 'mkdir -p ~/PhytoDex/models/flowers'
scp models/flowers/model.tflite models/flowers/metadata.json models/flowers/labels.json models/flowers/metrics.json phytodex@phytodex.local:~/PhytoDex/models/flowers/
```

Keep the complete results ZIP and its license/source records on the Mac. Adjust `~/PhytoDex` to `~/PhytoDex-ai-test` if you used the separate checkout. On the Pi:

```bash
cd ~/PhytoDex
source .venv-ai/bin/activate
uname -m
python3 --version
python -m pip install -r requirements-vision.txt
python -c "from ai_edge_litert.interpreter import Interpreter; print('LiteRT import OK')"
```

The Pi should report `aarch64` for 64-bit Raspberry Pi OS. If there is no wheel for the installed Python/architecture, preserve the working typed assistant and check the supported wheels on the LiteRT PyPI page. Do not install the full training environment on the Pi just to bypass a runtime install failure. This kit's runtime was not tested on your physical Pi.

Restart `run_ai.py` after copying model files. From the Mac, replace the photo path with one of your actual JPEG/PNG files:

```bash
curl -s http://phytodex.local:5001/api/identify -F 'image=@/absolute/path/to/your/flower.jpg'
```

Success: `source: local_mobilenetv2`, a candidate list, a latency value, and either `candidate` or `uncertain`. This endpoint operates without cloud internet once the packages and weights are installed. A `503` means the model/runtime bundle is missing or incompatible; it is not a plant prediction.

## 12 Connect the existing capture endpoint

This is an optional new API contract. Tell the backend/frontend owners before they integrate it. On a branch with the extracted scaffold, run:

```bash
python scripts/integrate_vision.py
git diff -- app.py
```

The script registers the prepared blueprint and refuses unfamiliar app layouts. The frontend can keep its existing `POST /api/capture` upload, then submit the returned numeric ID:

```bash
curl -s http://phytodex.local:5000/api/identify \
  -H 'Content-Type: application/json' \
  -d '{"capture_id":1}'
```

Use the real ID returned by capture; 1 is only an example. The route resolves the stored filename through the backend database and never accepts an arbitrary server path/URL. It does not modify the database schema or invent a PlantDex ID. Present candidates for manual confirmation. The existing `captures.status` remains `stored`; persisting classification history would be a separate backend change.

Why: image storage and model inference stay distinct, while the UI can use the capture flow your teammate already wrote. Avoid two routes competing to do uploads in different formats.

## 13 If you actually need houseplant recognition

Do not rename flower labels to pothos/monstera; that does not retrain anything. Choose 3–5 real target categories together. For a pilot, aim for 100–300 diverse, properly labeled images per category across many different specimens, backgrounds and sessions; those counts are starting targets, not an accuracy guarantee. Use your own photos or data whose terms permit your use. Keep a record of source URL, creator, license, label and specimen/group ID. Do not scrape arbitrary image search thumbnails and assume they are reusable.

Organize photos as `ml/data/houseplants/pothos/specimen001/001.jpg`, `.../pothos/specimen002/001.jpg`, `.../monstera/specimen001/001.jpg`, and so on. Put all images of one physical specimen in the same specimen folder, even across sessions. Have someone check labels and remove ambiguous/mislabeled images. The script requires at least five groups and 20 unique images per class just to operate; that minimum is not enough to claim robust performance.

Then run the existing code, with no code edits:

```bash
python ml/prepare_data.py --source ml/data/houseplants --out ml/data/houseplants-manifest.json
python ml/train.py --manifest ml/data/houseplants-manifest.json --out models/houseplants --epochs 8
```

Copy that bundle to the Pi and set `VISION_MODEL_DIR=models/houseplants` in `.env.ai`; restart the service. Retest the actual classes and unsupported objects. Keep the flower demo separate in naming and reporting. Training data acquisition/labeling and your account credentials are the inputs you still need to supply; the code cannot manufacture trustworthy labels or access rights.

## Completion checklist

- Live assistant returns the agreed structure, with explicit uncertainty.
- Empty/invalid requests receive useful 400/415 responses.
- Offline fallback is visibly labeled and works without a key/network.
- Six live evaluation cases have been read, not just schema-checked.
- Frontend and backend agree on field names and optional image contract.
- No secrets, datasets, or model artifacts are staged in Git.
- Pi serves the endpoint after a service restart.
- If vision is included: real training metrics are reviewed, labels/hash match, new capture-device photos are evaluated, and no general-species accuracy claim is made from the five-category demo.
