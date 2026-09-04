import os
os.environ["TF_USE_LEGACY_KERAS"] = "1"

import json
import tensorflow as tf

Size = (224, 224)
BATCH_SIZE = 32
DATASET_PATH = "dataset/"
Base_dir = os.path.dirname(os.path.abspath(__file__))
MODEL_OUT = os.path.join(Base_dir, "modelo_lumea_comida.h5")
CLASSES_OUT = os.path.join(Base_dir, "clases.json")

training = tf.keras.utils.image_dataset_from_directory(
    DATASET_PATH,
    subset="training",
    validation_split=0.2,
    image_size=Size,
    batch_size=BATCH_SIZE,
    seed=123,
)
validation = tf.keras.utils.image_dataset_from_directory(
    DATASET_PATH,
    subset="validation",
    validation_split=0.2,
    image_size=Size,
    batch_size=BATCH_SIZE,
    seed=123,
)

classes = training.class_names
print(f"Clases de entrenamiento ({len(classes)}): {classes}")

with open(CLASSES_OUT, "w", encoding="utf-8") as f:
    json.dump(classes, f)

# ==== Red neuronal - transfer learning sobre MobileNetV2 ====
data_argumentation = tf.keras.Sequential([
    tf.keras.layers.RandomFlip("horizontal_and_vertical"),
    tf.keras.layers.RandomRotation(0.2),
    tf.keras.layers.RandomZoom(0.2),
])
base_model = tf.keras.applications.MobileNetV2(input_shape=Size + (3,), include_top=False, weights='imagenet')
base_model.trainable = False

input_layer = tf.keras.layers.Input(shape=Size + (3,))
x = data_argumentation(input_layer)
x = tf.keras.applications.mobilenet_v2.preprocess_input(x)
model = base_model(x, training=False)
model = tf.keras.layers.GlobalAveragePooling2D()(model)
output_layer = tf.keras.layers.Dense(len(classes), activation='softmax')(model)
model = tf.keras.Model(inputs=input_layer, outputs=output_layer)

optimizer = tf.keras.optimizers.Adam(learning_rate=0.0001)
model.compile(optimizer=optimizer, loss='sparse_categorical_crossentropy', metrics=['accuracy'])

early_stopping = tf.keras.callbacks.EarlyStopping(
    monitor='val_loss', min_delta=0.001, patience=5, verbose=1, restore_best_weights=True
)
reduce_lr = tf.keras.callbacks.ReduceLROnPlateau(
    monitor='val_loss', factor=0.2, verbose=1, patience=3, min_lr=0.00001
)
checkpoint = tf.keras.callbacks.ModelCheckpoint(
    MODEL_OUT, save_best_only=True, monitor='val_loss', verbose=1
)

history = model.fit(
    training,
    validation_data=validation,
    epochs=10,
    callbacks=[early_stopping, reduce_lr, checkpoint],
)

# ==== Fine-tuning ====
base_model.trainable = True
for layer in base_model.layers[:100]:
    layer.trainable = False

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=1e-5),
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy'],
)
fine_tune_epochs = 10
total_epochs = 10 + fine_tune_epochs

fine_tuning_history = model.fit(
    training,
    validation_data=validation,
    epochs=total_epochs,
    initial_epoch=len(history.epoch),
    callbacks=[early_stopping, reduce_lr, checkpoint],
)
