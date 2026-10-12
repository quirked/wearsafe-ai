"""Streaming inference engine (demo_v0, PRELIMINARY): ACC at 32 Hz (m/s^2, E4 1/64 g data) and optional BVP at 64 Hz in,
one decision per second out. Uses exactly the offline code: wearsafe.features (motion v1+v2, physiology), the fusion
rules in wearsafe.fusion / config/fusion_v0.yaml, and the saved models.

Per decision second t (t >= 2):
  motion   : 2 s window [t-2, t) -> features v1+v2 -> motion probability -> alarm (>= deploy threshold)
  context  : 5 s window [t-5, t) -> context class (shown only; never suppresses)
  physio   : every 15 s once >= 30 s exist: 30 s BVP window -> SQI, HR, hr_rel_baseline (strictly past windows),
             acc_mag_std over the same 30 s -> status uncertain / elevated / normal / unknown (PLACEHOLDER rule)
  alert    : V0-base   -> prompt at the alarm (30 s refractory, keyed on alarm time)
             V0-stillness -> the alarm waits 5 s; prompt only if acc_mag_std over [t, t+5) <= gate threshold
  risk     : NONE / CHECK / HIGH (prompt and physiology 'elevated' at the alarm time)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from wearsafe import features as F
from wearsafe import fusion


@dataclass
class EngineConfig:
    motion_threshold: float
    gate_threshold: float
    features_cfg: dict
    refractory_s: float = 30.0
    stillness_s: float = 5.0
    fs_acc: int = 32
    fs_bvp: int = 64
    phys_window_s: int = 30
    phys_step_s: int = 15


@dataclass
class StreamingEngine:
    motion_bundle: dict
    context_bundle: dict | None
    cfg: EngineConfig
    acc: np.ndarray = field(default_factory=lambda: np.zeros((0, 3)))
    bvp: np.ndarray = field(default_factory=lambda: np.zeros(0))
    t: int = 0
    phys_hist: list = field(default_factory=list)            # (start, end, hr_mean, uncertain_by_physiology)
    phys_status: str = "unknown"
    phys_status_at: dict = field(default_factory=dict)       # t -> status in force at t
    last_prompt: dict = field(default_factory=lambda: {"base": -np.inf, "stillness": -np.inf})
    pending: list = field(default_factory=list)              # stillness: alarm times awaiting the 5 s check

    def push(self, acc_m_s2: np.ndarray, bvp: np.ndarray | None = None) -> list[dict]:
        self.acc = np.vstack([self.acc, np.asarray(acc_m_s2, dtype=float).reshape(-1, 3)])
        if bvp is not None:
            self.bvp = np.concatenate([self.bvp, np.asarray(bvp, dtype=float).reshape(-1)])
        out = []
        while (self.t + 1) * self.cfg.fs_acc <= len(self.acc):
            self.t += 1
            out.append(self._step(self.t))
        return out

    # ---- internals -------------------------------------------------------------------------------------------
    def _motion(self, t):
        fs = self.cfg.fs_acc
        a = self.acc[(t - 2) * fs:t * fs]
        s = fusion.e4_sat_axes(a)
        f = {**F.motion_features(a, fs, s.any(axis=1)), **F.saturation_features_v2(a, fs, s)}
        X = pd.DataFrame([f])[self.motion_bundle["features"]]
        return float(self.motion_bundle["model"].predict_proba(X)[:, 1][0])

    def _context(self, t):
        if self.context_bundle is None or t < 5:
            return "unknown"
        fs = self.cfg.fs_acc
        a = self.acc[(t - 5) * fs:t * fs]
        f = F.motion_features(a, fs, fusion.e4_sat_axes(a).any(axis=1))
        X = pd.DataFrame([f])[self.context_bundle["features"]]
        return str(self.context_bundle["model"].predict(X)[0])

    def _physiology(self, t):
        c = self.cfg
        if t < c.phys_window_s or (t - c.phys_window_s) % c.phys_step_s or len(self.bvp) < t * c.fs_bvp:
            return
        s0 = t - c.phys_window_s
        ph = F.physiology_features(self.bvp[s0 * c.fs_bvp:t * c.fs_bvp], c.fs_bvp, c.features_cfg)
        mag = np.sqrt((self.acc[s0 * c.fs_acc:t * c.fs_acc] ** 2).sum(axis=1))
        acc_std = float(mag.std())
        base_s = c.features_cfg["physiology"]["baseline_s"]
        rel = np.nan
        if s0 >= base_s and np.isfinite(ph["hr_mean"]):
            good = [h for (st, en, h, unc) in self.phys_hist if not unc and np.isfinite(h) and en <= s0 and st >= s0 - base_s]
            if good:
                rel = ph["hr_mean"] - float(np.median(good))
        self.phys_hist.append((s0, t, ph["hr_mean"], bool(ph["physiology_uncertain"])))
        self.phys_status = str(fusion.physiology_status([ph["ppg_sqi"]], [acc_std], [rel], c.gate_threshold)[0])

    def _step(self, t):
        self._physiology(t)
        self.phys_status_at[t] = self.phys_status
        res = {"t": t, "p_motion": np.nan, "alarm": False, "context": self._context(t), "phys_status": self.phys_status,
               "prompt_base": False, "prompt_stillness": False, "risk_base": "NONE", "risk_stillness": "NONE",
               "alert_state": "idle", "stillness_alarm_t": None}
        if t >= 2:
            p = self._motion(t)
            res["p_motion"], res["alarm"] = p, p >= self.cfg.motion_threshold
            if res["alarm"] and t - self.last_prompt["base"] >= self.cfg.refractory_s:
                self.last_prompt["base"] = t
                res["prompt_base"] = True
                res["risk_base"] = fusion.risk_level(True, self.phys_status)
            if res["alarm"]:
                self.pending.append(t)
        still_ready = [ta for ta in self.pending if ta + self.cfg.stillness_s <= t]
        self.pending = [ta for ta in self.pending if ta + self.cfg.stillness_s > t]
        fs = self.cfg.fs_acc
        for ta in still_ready:
            mag = np.sqrt((self.acc[ta * fs:(ta + int(self.cfg.stillness_s)) * fs] ** 2).sum(axis=1))
            if mag.std() <= self.cfg.gate_threshold and ta - self.last_prompt["stillness"] >= self.cfg.refractory_s:
                self.last_prompt["stillness"] = ta
                res["prompt_stillness"] = True
                res["stillness_alarm_t"] = ta
                res["risk_stillness"] = fusion.risk_level(True, self.phys_status_at.get(ta, "unknown"))
        if self.pending:
            res["alert_state"] = "pending_stillness_check"
        if res["prompt_base"] or res["prompt_stillness"]:
            res["alert_state"] = "prompt_are_you_safe"
        return res
