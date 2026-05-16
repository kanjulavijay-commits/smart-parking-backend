"""
ai_engine/ml_models/random_forest.py

Random Forest model for parking slot availability prediction.

What it does:
  Given: hour of day, day of week, month, lot name, zone name, is_weekend
  Predicts: probability that a slot will be occupied (0.0–1.0)

Why Random Forest for this task?
  - Works well on tabular data with mixed features (numbers + categories)
  - Handles small datasets well (even 100 bookings gives useful signal)
  - Interpretable: can explain WHY a slot is predicted busy
  - No GPU needed — trains in seconds on CPU
  - Robust to missing values and outliers

How it connects to your system:
  → User visits FindParking at 9am on Monday
  → RF predicts "Zone A will be 82% full — try Zone B instead"
  → System highlights Zone B slots as recommended
"""

import os
import pickle
import numpy as np


MODEL_PATH = os.path.join("ai_engine", "checkpoints", "random_forest.pkl")
FEATURE_COLS = ["hour", "day_of_week", "month", "is_weekend", "lot_encoded", "zone_encoded"]
TARGET_COL   = "is_occupied"


class ParkingAvailabilityRF:
    """
    Random Forest wrapper with fit / predict / save / load interface.
    Encodes categorical features (lot_name, zone_name) automatically.
    """

    def __init__(self, n_estimators=100, max_depth=10, random_state=42):
        from sklearn.ensemble import RandomForestClassifier
        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=random_state,
            class_weight="balanced",
            n_jobs=-1,
        )
        self._lot_encoder  = {}
        self._zone_encoder = {}
        self.feature_importances_ = None
        self.train_accuracy_ = None
        self.val_accuracy_   = None

    # ─── Encoding ─────────────────────────────────────────────────────────────

    def _encode(self, df):
        """Label-encode lot_name and zone_name columns."""
        df = df.copy()
        df["lot_encoded"]  = df["lot_name"].map(self._lot_encoder).fillna(-1).astype(int)
        df["zone_encoded"] = df["zone_name"].map(self._zone_encoder).fillna(-1).astype(int)
        return df[FEATURE_COLS].fillna(0)

    def _build_encoders(self, df):
        lots  = df["lot_name"].unique()
        zones = df["zone_name"].unique()
        self._lot_encoder  = {name: i for i, name in enumerate(sorted(lots))}
        self._zone_encoder = {name: i for i, name in enumerate(sorted(zones))}

    # ─── Training ─────────────────────────────────────────────────────────────

    def fit(self, df, val_df=None):
        """
        Train on a DataFrame produced by BookingHistoryDataset.
        df must have columns: hour, day_of_week, month, is_weekend,
                              lot_name, zone_name, is_occupied
        """
        if df.empty:
            raise ValueError("Empty dataframe — not enough booking data to train.")

        self._build_encoders(df)
        X = self._encode(df)
        y = df[TARGET_COL].values

        self.model.fit(X, y)
        self.feature_importances_ = dict(zip(FEATURE_COLS, self.model.feature_importances_))

        from sklearn.metrics import accuracy_score
        self.train_accuracy_ = accuracy_score(y, self.model.predict(X))

        if val_df is not None and not val_df.empty:
            X_val = self._encode(val_df)
            y_val = val_df[TARGET_COL].values
            self.val_accuracy_ = accuracy_score(y_val, self.model.predict(X_val))

        return self

    # ─── Prediction ───────────────────────────────────────────────────────────

    def predict_proba(self, hour, day_of_week, month, lot_name="", zone_name=""):
        """
        Predict occupancy probability for a given time + location.

        Returns:
            float: probability slot is occupied (0.0 = definitely free, 1.0 = definitely busy)
        """
        import pandas as pd
        row = pd.DataFrame([{
            "hour": hour,
            "day_of_week": day_of_week,
            "month": month,
            "is_weekend": int(day_of_week >= 5),
            "lot_name": lot_name,
            "zone_name": zone_name,
        }])
        X = self._encode(row)
        prob = self.model.predict_proba(X)[0]
        # prob[0] = vacant probability, prob[1] = occupied probability
        return float(prob[1]) if len(prob) > 1 else float(prob[0])

    def predict_availability(self, hour, day_of_week, month, lot_name="", zone_name=""):
        """
        High-level prediction: returns availability info dict for UI display.
        """
        occ_prob = self.predict_proba(hour, day_of_week, month, lot_name, zone_name)
        availability = 1.0 - occ_prob

        if availability >= 0.7:
            status = "high"
            label  = "Usually available"
        elif availability >= 0.4:
            status = "medium"
            label  = "Moderate availability"
        else:
            status = "low"
            label  = "Usually busy — book in advance"

        return {
            "occupancy_probability": round(occ_prob, 3),
            "availability_probability": round(availability, 3),
            "status": status,
            "label": label,
            "hour": hour,
            "day_of_week": day_of_week,
        }

    def top_features(self):
        """Return feature importances sorted by importance."""
        if not self.feature_importances_:
            return {}
        return dict(sorted(self.feature_importances_.items(), key=lambda x: x[1], reverse=True))

    # ─── Persistence ──────────────────────────────────────────────────────────

    def save(self, path=MODEL_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({
                "model":        self.model,
                "lot_encoder":  self._lot_encoder,
                "zone_encoder": self._zone_encoder,
                "feature_importances": self.feature_importances_,
                "train_accuracy": self.train_accuracy_,
                "val_accuracy":   self.val_accuracy_,
            }, f)
        return path

    @classmethod
    def load(cls, path=MODEL_PATH):
        with open(path, "rb") as f:
            data = pickle.load(f)
        obj = cls.__new__(cls)
        obj.model                 = data["model"]
        obj._lot_encoder          = data["lot_encoder"]
        obj._zone_encoder         = data["zone_encoder"]
        obj.feature_importances_  = data.get("feature_importances_", {})
        obj.train_accuracy_       = data.get("train_accuracy")
        obj.val_accuracy_         = data.get("val_accuracy")
        return obj

    @classmethod
    def is_trained(cls, path=MODEL_PATH):
        return os.path.exists(path)
