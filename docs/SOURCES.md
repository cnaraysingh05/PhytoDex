# Sources and model provenance

Inspected September 26, 2026. Read model availability again when creating your key; account access and quota are not guaranteed by documentation.

- Team repository: https://github.com/cnaraysingh05/PhytoDex
- Existing assistant: https://github.com/cnaraysingh05/PhytoDex/blob/9202f9e73a108af212e4071e7cffb0f2fa509333/assistant.py
- Backend scaffold: https://github.com/cnaraysingh05/PhytoDex/blob/033aaf339eb3ddb1b89e7b2d1d383d75f3132656/phytodex-backend-scaffold.zip
- Gemini 2.5 access note: https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash
- Current configured model documentation: https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash
- Structured output contract: https://ai.google.dev/gemini-api/docs/generate-content/structured-output
- TensorFlow transfer learning and MobileNetV2 preprocessing: https://www.tensorflow.org/tutorials/images/transfer_learning
- MobileNetV2 architecture/API: https://www.tensorflow.org/api_docs/python/tf/keras/applications/MobileNetV2
- Flower dataset catalog: https://www.tensorflow.org/datasets/catalog/tf_flowers
- Official image archive: https://storage.googleapis.com/download.tensorflow.org/example_images/flower_photos.tgz
- Raspberry Pi LiteRT Python inference: https://developers.google.com/edge/litert/microcontrollers/python
- Runtime wheel compatibility: https://pypi.org/project/ai-edge-litert/

Source selection: keep the team's existing Gemini provider for typed guidance. Reuse MobileNetV2's published pretrained features for the optional narrow classifier. The five-category flower dataset makes the training pipeline reproducible; it does not match the complete houseplant catalog. Do not represent a crop-disease model as a general plant species model either.

The download script preserves the flower archive's LICENSE.txt and records the archive SHA-256 and URL. Keep image-level attribution and applicable license terms if redistributing images. A software library license does not automatically license its training images or every set of weights. Review upstream terms before broader redistribution; this kit ships neither third-party images nor trained weights.

The trained bundle records labels, preprocessing, model hash, split-manifest hash and validation/test results. Keep these with each version. TensorFlow's selected weights are downloaded by its official Keras implementation. Full training and source downloads require internet; inference with the deployed local image model does not.
