"""Small original NumPy Double-Q learner with optional predictive encoder gradients.

Inspired by MR.Q's reward/transition representation objectives, not a reproduction.
No upstream implementation or weights are copied. No imagined-rollout planning.
"""

import numpy as np

from alive.learning.environment import ACTIONS, FEATURES


class Controller:
    def __init__(self, seed=11, latent_weight=0.0, reward_weight=0.0):
        self.latent_weight = latent_weight
        self.reward_weight = reward_weight
        d, h, a = len(FEATURES), 32, len(ACTIONS)
        rng = np.random.default_rng(seed)
        self.p = {}
        for name, shape in {
            "E": (d, h),
            "Q": (h, a),
            "T": (h + a, h),
            "R": (h + a, 1),
            "O": (h + a, d),
        }.items():
            self.p[name] = rng.normal(0, 1 / np.sqrt(shape[0]), shape)
            self.p[name + "b"] = np.zeros(shape[1])
        self.target = {k: v.copy() for k, v in self.p.items()}
        self.m = {k: np.zeros_like(v) for k, v in self.p.items()}
        self.v = {k: np.zeros_like(v) for k, v in self.p.items()}
        self.updates = 0

    def encode(self, x, target=False):
        p = self.target if target else self.p
        return np.maximum(0, x @ p["E"] + p["Eb"])

    def q(self, x, target=False):
        p = self.target if target else self.p
        return self.encode(x, target) @ p["Q"] + p["Qb"]

    def choose(self, state, mask):
        if not np.any(mask):
            raise ValueError("No permitted action")
        return int(np.argmax(np.where(mask, self.q(state), -np.inf)))

    def predict(self, state, action):
        joint = np.concatenate([self.encode(state), np.eye(len(ACTIONS))[action]])
        return {
            "next_state": (joint @ self.p["O"] + self.p["Ob"]).tolist(),
            "reward": float((joint @ self.p["R"] + self.p["Rb"])[0]),
            "next_latent": (joint @ self.p["T"] + self.p["Tb"]).tolist(),
        }

    def gradients(self, batch):
        x, actions, rewards, next_x, done, next_mask = batch
        n = len(x)
        p = self.p
        z = self.encode(x)
        q = z @ p["Q"] + p["Qb"]
        greedy = np.argmax(np.where(next_mask, self.q(next_x), -np.inf), axis=1)
        next_q = self.q(next_x, target=True)[np.arange(n), greedy]
        # Both Double-Q target selection and target-encoder transitions are stop-gradient.
        target = rewards + 0.95 * (1 - done) * next_q
        diff = q[np.arange(n), actions] - target
        dq = np.zeros_like(q)
        dq[np.arange(n), actions] = np.clip(diff, -2, 2) / n
        grads = {"Q": z.T @ dq, "Qb": dq.sum(axis=0)}
        dz = dq @ p["Q"].T
        joint = np.concatenate([z, np.eye(len(ACTIONS))[actions]], axis=1)
        targets = {"T": self.encode(next_x, target=True), "R": rewards[:, None], "O": next_x}
        weights = {"T": self.latent_weight, "R": self.reward_weight, "O": 0.0}
        losses = {
            "td_huber": float(np.mean(np.where(abs(diff) < 2, 0.5 * diff**2, 2 * abs(diff) - 2)))
        }
        for head in ["T", "R", "O"]:
            error = joint @ p[head] + p[head + "b"] - targets[head]
            derivative = error / error.size
            # Probes are trained identically in every arm. Only specified predictive
            # gradients can reach the shared encoder; O is a detached diagnostic probe.
            grads[head], grads[head + "b"] = joint.T @ derivative, derivative.sum(axis=0)
            dz += weights[head] * (derivative @ p[head].T)[:, : z.shape[1]]
            losses[head + "_mse"] = float(np.mean(error**2))
        dz *= z > 0
        grads["E"], grads["Eb"] = x.T @ dz, dz.sum(axis=0)
        return grads, losses

    def update(self, batch):
        grads, losses = self.gradients(batch)
        norm = np.sqrt(sum(float(np.sum(g * g)) for g in grads.values()))
        scale = min(1, 10 / max(norm, 1e-12))
        self.updates += 1
        for key, grad in grads.items():
            grad = grad * scale
            self.m[key] = 0.9 * self.m[key] + 0.1 * grad
            self.v[key] = 0.999 * self.v[key] + 0.001 * grad**2
            m = self.m[key] / (1 - 0.9**self.updates)
            v = self.v[key] / (1 - 0.999**self.updates)
            self.p[key] -= 0.002 * m / (np.sqrt(v) + 1e-8)
        if self.updates % 100 == 0:
            self.target = {k: v.copy() for k, v in self.p.items()}
        return losses

    def save(self, path):
        np.savez_compressed(path, **self.p, **{"target_" + k: v for k, v in self.target.items()})

    def restore(self, path):
        with np.load(path, allow_pickle=False) as values:
            for key in self.p:
                self.p[key] = values[key].copy()
                self.target[key] = values["target_" + key].copy()


def arrays(transitions):
    if not transitions or any(t["split"] != "train" for t in transitions):
        raise ValueError("Training accepts completed training-split transitions only")
    return (
        np.asarray([t["state"] for t in transitions]),
        np.asarray([t["action"] for t in transitions], dtype=int),
        np.asarray([t["reward"] for t in transitions]),
        np.asarray([t["next_state"] for t in transitions]),
        np.asarray([t["done"] for t in transitions], dtype=float),
        np.asarray([t["next_valid_actions"] for t in transitions], dtype=bool),
    )
