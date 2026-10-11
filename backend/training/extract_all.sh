#!/bin/sh
# Извлечение признаков всех выборок для экспериментов. Журнал: data/extract.log
cd "$(dirname "$0")/.." || exit 1
X=".venv/bin/python -u -m training.extract_features"
D="data/dusha/data/test-00000-*.parquet"
R="data/resd/data/test-*.parquet"
{
$X --parquet "$R" --out data/features/resd_test_raw.npz
$X --parquet "$D" --out data/features/dusha_test_raw.npz
$X --parquet "data/resd/data/train-*.parquet" --out data/features/resd_train_raw.npz
for i in 0 1 2 3 4 5; do
  $X --parquet "data/dusha/data/train-0000$i-*.parquet" --out "data/features/dusha_train_raw_$i.npz"
done
$X --parquet "$R" --out data/features/resd_test_denoise.npz --preprocess denoise
$X --parquet "$D" --out data/features/dusha_test_denoise.npz --preprocess denoise
$X --parquet "$R" --out data/features/resd_test_norm.npz --preprocess norm
$X --parquet "$D" --out data/features/dusha_test_norm.npz --preprocess norm
echo ALL_DONE
} > data/extract.log 2>&1
