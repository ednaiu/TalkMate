# Talk Mate

Talk Mate is a public speaking practice app for iPhone and Android. Record a rehearsal, optionally attach PDF slides, and review your pace, filler words, voice metrics, transcript and suggestions for the next attempt.

Speech recognition and analysis run on a self-hosted Python backend. Audio is sent to that backend rather than a third-party speech API. Model weights are downloaded on first use. The project began as a bachelor's thesis prototype; the original presentation is included in the repository.

## Portfolio and case study

- [Edna Iusupova: portfolio](https://ednaiu.github.io/)
- [Talk Mate: project case study](https://ednaiu.github.io/talk-mate/)
- [App screens](https://ednaiu.github.io/talk-mate/#screens)
- [Speech recognition and models](https://ednaiu.github.io/talk-mate/#models)

## Technical documentation

- [English screenshot inventory](docs/screens/current-ios-en/README.md)
- [Russian screenshot inventory](docs/screens/current-ios/README.md)
- [Model evaluation and experiments](docs/MODELS.md) (Russian)
- [User guide](docs/USER_GUIDE.md) (Russian)
- [Repository structure and local artifacts](docs/REPOSITORY.md) (Russian)

Each current screenshot set contains 38 screens and states captured in the iOS Simulator with demonstration data. These captures do not represent analysis of real user recordings. Legal documents shown in the app are drafts.

## Repository

| Directory | Contents |
| --- | --- |
| `android/` | Kotlin app, WAV recorder and API client |
| `ios/` | SwiftUI app, native audio recorder and API client |
| `backend/talkmate/` | Flask application API and admin interface |
| `backend/speech_analysis/` | Speech recognition, audio metrics, emotion and slide analysis |
| `backend/training/` | Training, dataset preparation and model benchmarks |
| `docs/` | Screenshots, model reports, design notes and user documentation |

Datasets, downloaded models, uploads, the local database and Python environment are excluded from Git. Keep them when cleaning generated build files. Screenshot ZIP exports are written to the ignored `output/screens/` directory.

## Architecture

The backend has two services sharing a database:

- **Application service, port 5050:** authentication, recordings, feedback, articles, recommendations, settings and administration.
- **Analysis service, port 5051:** model inference and speech metrics through `POST /analyze`.

The application service separates HTTP controllers, business services, repositories, SQLAlchemy models and database connections. Core tables include `user`, `speech`, `feedback`, `article`, `recommendation` and `threshold`. Administrators can adjust analysis thresholds without changing the application code.

The analysis service binds to `127.0.0.1` by default. If deployed on a separate machine, configure its address and a shared `ANALYSIS_TOKEN`; it is intended for internal access. Both services support MySQL, with a shared SQLite file as the local fallback.

## Run the backend

Requirements: Python 3.12, Docker for the supplied MySQL setup, and ffmpeg for audio formats other than WAV.

```sh
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -r requirements-ml.txt
cp .env.example .env
# Edit .env: replace SECRET_KEY and the default admin credentials.
docker compose up -d
./run.sh
```

MySQL is exposed locally on port `3307`. The environment file selects it through `DATABASE_URL`. If `DATABASE_URL` is unset, both services use the SQLite fallback. `ANALYSIS_INPROCESS=1` runs analysis inside the application service instead of starting a separate process.

### Speech recognition

Russian speech uses **GigaAM-v3 e2e CTC**, selected after a project benchmark of eight candidates. English speech uses **Parakeet TDT 0.6b v3**. The server detects the speech language and applies the corresponding recognizer, filler vocabulary and pace thresholds. Long recordings are split at pauses into chunks of up to 25 seconds.

`RECOGNIZER` selects the recognition mode:

| Value | Behavior |
| --- | --- |
| `auto` (default) | Use `ASR_MODEL` through `onnx-asr`; fall back to Vosk if the package or model is unavailable |
| `onnx` | Use only the model selected by `ASR_MODEL` |
| `vosk` | Use a local Vosk model |

The default `ASR_MODEL` is `gigaam-v3-e2e-ctc`. For the Russian Vosk fallback, download [vosk-model-small-ru-0.22](https://alphacephei.com/vosk/models) and extract it under `backend/models/`.

The Russian ONNX model download is approximately 900 MB. The project measured roughly 0.03 seconds of processing per second of audio on its benchmark CPU. This is a local measurement, not a latency guarantee. Dataset details, word error rates and filler retention results are in [MODELS.md](docs/MODELS.md).

### Emotion model

`EMOTION_BACKEND=talkmate` uses the `Aniemore/wavlm-emotion-russian-resd` encoder with a custom classification head trained on Dusha and RESD. The head is included at `backend/speech_analysis/weights/emotion_head.pt`; the encoder is downloaded on first use, approximately 1.2 GB.

The project evaluation reported an accuracy increase from 16.5% to 78.2% on its spontaneous-speech evaluation set. See [the evaluation report](docs/MODELS.md) for the method and scope. An emotion label is a model estimate from voice characteristics, not a reliable statement about the speaker's feelings.

Set `EMOTION_BACKEND=aniemore` to use the original model or `off` to disable emotion inference. If loading fails, other metrics remain available and the emotion result is marked as undetermined.

### Administration and password recovery

Open `http://localhost:5050/admin`. The initial account is created from `ADMIN_EMAIL` and `ADMIN_PASSWORD`. The admin interface supports articles, analysis thresholds and user details.

Password recovery sends a six-digit code by email. Codes expire after 15 minutes, are stored as hashes and stop working after five failed attempts. A new request is allowed after one minute. The response does not reveal whether an email address is registered.

Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` and `SMTP_FROM` in `.env`. When `SMTP_HOST` is empty, the server logs the recovery code instead of sending email. This fallback is for local development.

## Build for iPhone

Use Xcode with the iOS SDK and [XcodeGen](https://github.com/yonaskolb/XcodeGen). The deployment target is iOS 17.0. The Xcode project is generated from `ios/project.yml` and is not tracked in Git.

```sh
brew install xcodegen
cd ios
xcodegen generate
open TalkMate.xcodeproj
```

Run the app from Xcode. The Simulator connects to `http://localhost:5050`, which points to the backend on the same Mac.

### Install on a physical iPhone

1. Add your Apple ID in Xcode under **Settings > Accounts**.
2. Enable **Developer Mode** under **Settings > Privacy & Security** on the iPhone.
3. Connect and unlock the phone, trust the Mac, then run:

```sh
cd ios
./install_on_iphone.sh
```

The script finds the signing account and device, builds, signs, installs and launches the app. It uses the Mac's LAN address for the backend. Keep both devices on the same network and run `backend/run.sh`. You can change the server address in the app's profile settings.

If prompted, trust the developer under **Settings > General > VPN & Device Management**. A free Apple development account generally requires reinstalling the signed build after seven days.

The iOS app stores authentication tokens in Keychain and records audio with `AVAudioRecorder`. Interface text uses the system font with Dynamic Type; the wordmark uses Manrope at weight 650.

## Build for Android

Requirements: Android Studio, or JDK 17+ with Android SDK 34.

```sh
cd android
./gradlew assembleDebug
# APK: app/build/outputs/apk/debug/app-debug.apk
```

The emulator connects to `http://10.0.2.2:5050`. For a physical device, supply the backend's LAN address when building:

```sh
./gradlew assembleDebug -PapiBaseUrl=http://192.168.1.10:5050
```

The address can also be changed in profile settings. Android uses system text fonts and retains Yeseva One and Poiret One for decorative wordmark elements. Font licenses are included with the platform resources. Both apps use the same backend, though their layouts can differ.

## Analysis methods

Implementation lives in `backend/speech_analysis/`.

| Metric or feature | Method and limitations |
| --- | --- |
| Pace | Recognized word count divided by recording duration in minutes. Language-specific reference ranges are configurable; the Russian default is 90-140 words per minute. These ranges are practice guides, not universal speaking standards. |
| Volume | RMS amplitude over speech regions, expressed in dBFS. Default boundaries are -30 dBFS for quiet speech and -12 dBFS for loud speech. Microphone gain and distance affect the result. |
| Pitch variation | Standard deviation in semitones of median pitch across half-second segments, using `librosa.yin`. Below 2 semitones is classified as monotonous. |
| Filler words | Language-specific words, phrases, hesitation sounds and prolonged vowels. Ambiguous words are counted only in specified punctuation contexts. Recognition errors can omit fillers. |
| Background noise | SNR estimate from the 90th and 10th percentiles of loudness in 64 ms frames. Below the configurable 15 dB default, feedback prioritizes recording conditions. The estimate is unavailable when there is insufficient loudness variation. |
| Clarity | Recognition confidence at recording, phrase and word level. It is affected by noise and microphone quality as well as speech. On 444 evaluation recordings, confidence had an absolute correlation of 0.67 with recognition error rate. |
| Emotion | WavLM features and a trained classification head over 8-second windows at 16 kHz. Window probabilities are averaged. Confidence thresholds reduce uncertain negative labels. Denoising is disabled because it reduced accuracy in the project evaluation. |
| Main idea | Local `cointegrated/rut5-base-absum` summarization, with an extractive fallback. The model download is approximately 900 MB. Set `MAIN_IDEA_BACKEND=extractive` to use the fallback directly. Short or fragmented transcripts may produce poor summaries. |
| Structure | Heuristics for an opening, transitions and a conclusion. Recordings with fewer than 40 words are not assessed. |
| Phrase review | Word timestamps are grouped into phrases, with phrase-level pace and emotion estimates. Short phrases are combined into spans of at least three seconds. |
| PDF slides | Text extraction and PP-OCRv5 OCR, followed by matching speech to slide text. Recorded slide changes take priority; otherwise matching uses lexical overlap and `multilingual-e5-small` embeddings. Results include time per slide, content coverage, read-aloud share, text density and small-font warnings. |

Without slide-change markers, the slide matcher assigned 94% of speaking time to the correct slide across four recorded talks in the project evaluation. This small evaluation does not establish performance on arbitrary presentations. Methods, datasets and limitations are documented in [MODELS.md](docs/MODELS.md).

## Training and evaluation

`training/extract_features.py` computes frozen encoder features once. `training/train_head.py` trains a classification head on those features; this produced the bundled weights.

`training/train_emotion.py` also supports unfreezing the encoder's upper layers for CUDA training:

```sh
cd backend
.venv/bin/python -m training.train_emotion \
    --dusha "data/dusha/data/train-*.parquet" --resd "data/resd/data/train-*.parquet" \
    --test-dusha "data/dusha/data/test-*.parquet" --test-resd "data/resd/data/test-*.parquet" \
    --unfreeze-layers 4 --epochs 8 --output models/wavlm-emotion-dusha
```

Train on Dusha and RESD together. Dusha contains four emotion classes; RESD supplies examples needed to retain fear, disgust and interest. Reproduction instructions and experiment results are in [MODELS.md](docs/MODELS.md).

### Feedback from app recordings

- `PUT /api/speeches/<id>/ratings/<metric>` accepts `{"verdict": "correct" | "wrong", "comment": "..."}`. Supported metrics include pace, volume, monotony, fillers, clarity, noise, emotion, main idea, structure, slides, transcript and overall review. `GET /api/speeches/<id>/ratings` returns the recording's ratings. Administrators can inspect `GET /api/admin/ratings/summary`.
- `PUT /api/consent` accepts `{"share_recordings": true}` to opt into using recordings for model improvement, or `false` to withdraw. Consent timestamps are stored. The consent wording and draft legal documents still require review before public release.
- `python -m training.export_dataset --out data/own_testset_draft` exports recordings from consenting users with draft model transcripts. Annotators must correct `.txt` files verbatim, retaining fillers and repetitions. Optional `.json` labels can include `{"pace": "slow|ok|fast", "noisy": false}`.
- `python -m training.own_testset --data data/own_testset` evaluates word error rate, filler and hesitation recall, pace error, and agreement with human pace/noise labels. Results are saved to `training/results/own_testset.json`.

## Tests

Run the suites appropriate to the component you change. Tests marked `real` require actual model dependencies and weights; device tests require a running simulator or connected device. Test counts are omitted because the suites are still growing.

```sh
cd backend
.venv/bin/python -m pytest
.venv/bin/python -m pytest -m real
TEST_DATABASE_URL='mysql+pymysql://talkmate:talkmate@127.0.0.1:3307/talkmate' \
    .venv/bin/python -m pytest tests/test_api.py tests/test_admin.py

cd ../android
./gradlew testDebugUnitTest
./gradlew connectedDebugAndroidTest

cd ../ios
xcodegen generate
xcodebuild -project TalkMate.xcodeproj -scheme TalkMate \
    -destination 'platform=iOS Simulator,name=iPhone 17' test
```

Replace the Simulator name with one installed on your Mac. UI scenarios use `FakeApi` for repeatable data without a live backend. The Android real-server test runs separately with `backend/run.sh` active:

```sh
cd android
./gradlew installDebug installDebugAndroidTest
adb shell am instrument -w -e class ru.itmo.talkmate.RealServerTest \
    -e serverUrl http://10.0.2.2:5050 \
    ru.itmo.talkmate.test/androidx.test.runner.AndroidJUnitRunner
```

It registers a user, uploads an audio fixture, checks analysis and statistics, and captures screenshots.

## Validation limits

- Recorder tests cover file output and pause behavior; model benchmarks use prerecorded audio. Microphone capture and analysis still need systematic checks on physical phones.
- The admin API has tests, but the browser interface has not received a full interaction review.
- Encoder fine-tuning was tested on a small model. A full run of the supplied encoder fine-tuning configuration was not completed on the development machine because of memory limits.
- Reported model quality comes from project evaluations on public datasets and recorded talks. Performance on recordings from app users has not yet been established.
