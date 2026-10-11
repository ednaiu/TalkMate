"""Разовый подбор настроек головы по проверочной части Dusha. Тестовые выборки здесь не используются."""
import json, sys, time
import numpy as np
from training.train_head import load_set, split_by_clip, train_head

dusha = load_set("data/features/dusha_train_raw_[0-5].npz"); resd = load_set("data/features/resd_train_raw.npz")
dt, dv = split_by_clip(dusha, 0.15, 0); rt, rv = split_by_clip(resd, 0.15, 0)
del dusha, resd
grid = {
    "base": {},
    "hidden512": dict(hidden=512),
    "hidden128": dict(hidden=128),
    "dropout0.5": dict(dropout=0.5),
    "dropout0.1": dict(dropout=0.1),
    "noise0": dict(feature_noise=0.0),
    "noise0.3": dict(feature_noise=0.3),
    "balance0.5": dict(balance=0.5),
    "balance0": dict(balance=0.0),
    "resd0.15": dict(resd_share=0.15),
    "resd0.5": dict(resd_share=0.5),
    "smooth0": dict(label_smoothing=0.0),
    "lr3e-3": dict(lr=3e-3),
    "lr3e-4": dict(lr=3e-4),
    "mean_only": dict(pooling="mean"),
    "last_layer": dict(layers="last"),
    "linear": dict(hidden=0),
}
out = {}
for name, kw in grid.items():
    t = time.time()
    _, _, hist = train_head({"dusha": dt, "resd": rt}, {"dusha": dv, "resd": rv}, log=lambda s: None, **kw)
    best = max(hist, key=lambda h: h["mean"])
    out[name] = {"dusha_val": best["dusha"], "resd_val": best["resd"], "epoch": best["epoch"], "last": hist[-1]["dusha"]}
    print("%-12s dusha_val %.4f (эпоха %2d, в конце %.4f)  resd_val %.4f  %.0f c" % (name, best["dusha"], best["epoch"], hist[-1]["dusha"], best["resd"], time.time() - t), flush=True)
json.dump(out, open("data/search.json", "w"), indent=1)
