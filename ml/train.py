"""Transfer learning, LiteRT export, validation threshold and held-out evaluation."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
import numpy as np
import tensorflow as tf
from PIL import Image, ImageOps

SIZE = 160


def read_image(path):
    with Image.open(path) as im:
        return np.asarray(ImageOps.exif_transpose(im).convert('RGB').resize(
            (SIZE, SIZE), Image.Resampling.BILINEAR), dtype=np.float32)


def make_model(classes, weights='imagenet'):
    base = tf.keras.applications.MobileNetV2(
        input_shape=(SIZE, SIZE, 3), include_top=False, weights=weights, alpha=0.5)
    base.trainable = False
    inputs = tf.keras.Input(shape=(SIZE, SIZE, 3), name='rgb_0_255')
    x = tf.keras.layers.Rescaling(1 / 127.5, offset=-1)(inputs)
    x = base(x, training=False)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dropout(.2)(x)
    outputs = tf.keras.layers.Dense(classes, activation='softmax')(x)
    return tf.keras.Model(inputs, outputs), base


def scores_report(probabilities, truth, labels, threshold):
    pred = probabilities.argmax(axis=1)
    accepted = probabilities.max(axis=1) >= threshold
    cm = np.zeros((len(labels), len(labels)), dtype=int)
    np.add.at(cm, (truth, pred), 1)
    precision = np.diag(cm) / np.maximum(cm.sum(axis=0), 1)
    recall = np.diag(cm) / np.maximum(cm.sum(axis=1), 1)
    f1 = 2 * precision * recall / np.maximum(precision + recall, 1e-9)
    return {'examples': len(truth), 'accuracy': float(np.mean(pred == truth)),
            'macro_f1': float(f1.mean()), 'coverage': float(accepted.mean()),
            'accepted_accuracy': float(np.mean(pred[accepted] == truth[accepted])) if accepted.any() else None,
            'confusion_matrix_rows_true_columns_predicted': cm.tolist(),
            'per_class': {l: {'precision': float(precision[i]), 'recall': float(recall[i]),
                              'f1': float(f1[i]), 'support': int(cm[i].sum())}
                          for i, l in enumerate(labels)}}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--manifest', default='ml/data/manifest.json')
    p.add_argument('--out', type=Path, default=Path('models/flowers'))
    p.add_argument('--epochs', type=int, default=8)
    p.add_argument('--batch-size', type=int, default=32)
    p.add_argument('--fine-tune-epochs', type=int, default=0)
    p.add_argument('--smoke', action='store_true', help='Random weights, 1 epoch; NOT a usable model')
    args = p.parse_args()
    if args.out.exists():
        raise SystemExit('Output exists. Use a fresh --out directory for a new experiment.')
    if args.epochs < 1 or args.batch_size < 1:
        raise SystemExit('epochs and batch-size must be positive')
    tf.keras.utils.set_random_seed(42)
    tf.config.threading.set_inter_op_parallelism_threads(2)
    tf.config.threading.set_intra_op_parallelism_threads(2)
    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text())
    root, labels = Path(manifest['root']), manifest['labels']
    rows = {s: [r for r in manifest['records'] if r['split'] == s] for s in ('train', 'val', 'test')}
    for split in rows:
        if set(r['label'] for r in rows[split]) != set(labels):
            raise ValueError(f'Every class must occur in {split}')
    args.out.mkdir(parents=True)

    def dataset(split):
        def gen():
            for r in rows[split]:
                yield read_image(root / r['path']), np.int32(labels.index(r['label']))
        ds = tf.data.Dataset.from_generator(gen, output_signature=(
            tf.TensorSpec((SIZE, SIZE, 3), tf.float32), tf.TensorSpec((), tf.int32)))
        ds = ds.apply(tf.data.experimental.assert_cardinality(len(rows[split])))
        if split == 'train':
            ds = ds.shuffle(min(len(rows[split]), 2048), seed=42)
            ds = ds.map(lambda x, y: (tf.image.random_flip_left_right(x), y), num_parallel_calls=1)
        options = tf.data.Options()
        options.threading.private_threadpool_size = 2
        return ds.batch(args.batch_size).with_options(options).prefetch(1)

    model, base = make_model(len(labels), None if args.smoke else 'imagenet')
    model.compile(optimizer=tf.keras.optimizers.Adam(.001),
                  loss='sparse_categorical_crossentropy', metrics=['accuracy'])
    model.fit(dataset('train'), validation_data=dataset('val'),
              epochs=1 if args.smoke else args.epochs,
              callbacks=[tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=3,
                                                          restore_best_weights=True)])
    if args.fine_tune_epochs and not args.smoke:
        model.save(args.out / 'head.keras')
        before = model.evaluate(dataset('val'), verbose=0)[0]
        base.trainable = True
        for layer in base.layers[:-20]:
            layer.trainable = False
        for layer in base.layers:
            if isinstance(layer, tf.keras.layers.BatchNormalization):
                layer.trainable = False
        model.compile(optimizer=tf.keras.optimizers.Adam(1e-5),
                      loss='sparse_categorical_crossentropy', metrics=['accuracy'])
        model.fit(dataset('train'), validation_data=dataset('val'), epochs=args.fine_tune_epochs,
                  callbacks=[tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=2,
                                                              restore_best_weights=True)])
        if model.evaluate(dataset('val'), verbose=0)[0] > before:
            model = tf.keras.models.load_model(args.out / 'head.keras')
    model.save(args.out / 'model.keras')
    saved = args.out / 'saved_model'
    model.export(str(saved), verbose=False)
    converter = tf.lite.TFLiteConverter.from_saved_model(str(saved))
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_types = [tf.float16]
    blob = converter.convert()
    (args.out / 'model.tflite').write_bytes(blob)
    interpreter = tf.lite.Interpreter(model_content=blob, num_threads=2)
    interpreter.allocate_tensors()
    inp, out = interpreter.get_input_details()[0], interpreter.get_output_details()[0]

    def predict(split):
        probabilities, truth = [], []
        for r in rows[split]:
            image = read_image(root / r['path'])[None]
            interpreter.set_tensor(inp['index'], image)
            interpreter.invoke()
            probabilities.append(interpreter.get_tensor(out['index'])[0])
            truth.append(labels.index(r['label']))
        return np.array(probabilities), np.array(truth)

    val_probs, val_truth = predict('val')
    # Choose using validation ONLY; never retune against held-out test results.
    threshold = 1.01  # No acceptable validation threshold -> always uncertain.
    for candidate in np.arange(.50, 1.0, .01):
        accepted = val_probs.max(axis=1) >= candidate
        if accepted.sum() >= 20 and np.mean(val_probs.argmax(axis=1)[accepted] == val_truth[accepted]) >= .90:
            threshold = float(round(candidate, 2))
            break
    if args.smoke:
        threshold = 1.01
    test_probs, test_truth = predict('test')
    probe = np.stack([read_image(root / r['path']) for r in rows['test'][:10]])
    keras_probs = model.predict(probe, verbose=0)
    delta = float(np.abs(keras_probs - test_probs[:len(probe)]).max())
    if delta > .05:
        raise RuntimeError(f'Keras / LiteRT output mismatch: {delta}; do not deploy this export')
    metadata = {
        'schema_version': 1, 'labels': labels, 'image_size': SIZE, 'input_dtype': 'float32',
        'input_range': [0, 255], 'normalization': 'inside_model', 'resize': 'PIL bilinear stretch',
        'threshold': threshold, 'model_sha256': hashlib.sha256(blob).hexdigest(),
        'base': 'MobileNetV2 alpha=0.5 ImageNet', 'smoke_only': args.smoke,
        'scope': 'Only the listed classes. Scores are not calibrated probabilities of correct identity.',
        'manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    }
    report = {'labels': labels, 'threshold': threshold, 'threshold_target': 'validation accepted accuracy >=0.90, n>=20',
              'validation': scores_report(val_probs, val_truth, labels, threshold),
              'test': scores_report(test_probs, test_truth, labels, threshold),
              'keras_litert_max_absolute_difference': delta,
              'limitations': ['Image-level flower split does not guarantee different specimens.',
                              'No out-of-distribution or real-Pi-photo accuracy measured.']}
    (args.out / 'metadata.json').write_text(json.dumps(metadata, indent=2))
    (args.out / 'metrics.json').write_text(json.dumps(report, indent=2))
    (args.out / 'labels.json').write_text(json.dumps(labels, indent=2))
    shutil.copyfile(manifest_path, args.out / 'training_manifest.json')
    license_file = root / 'LICENSE.txt'
    if license_file.exists():
        shutil.copyfile(license_file, args.out / 'DATASET_LICENSE.txt')
    (args.out / 'DATASET_SOURCE.json').write_text(json.dumps(manifest.get('provenance', {}), indent=2))
    print(json.dumps(report, indent=2))
    print('Export complete. Evaluate real camera photos before presenting identification accuracy.')


if __name__ == '__main__':
    main()
