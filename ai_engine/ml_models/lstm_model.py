"""
ai_engine/ml_models/lstm_model.py

LSTM (Long Short-Term Memory) for parking occupancy forecasting.

What it does:
  Given: occupancy % for the last 24 hours (one reading per hour)
  Predicts: occupancy % for the NEXT 4 hours

Why LSTM for this task?
  - LSTMs are designed for sequences — they "remember" patterns over time
  - Parking has strong temporal patterns (rush hour, lunch, weekends)
  - The LSTM learns: "After 8am occupancy spikes, 9-10am is always peak"
  - This lets you show users a "forecast bar" on the Find Parking page

Architecture:
  Input  → 24 time steps × 4 features (hour, day_of_week, occupancy, is_weekend)
  LSTM   → 2 layers, 64 hidden units
  Output → 4 predictions (next 4 hours occupancy %)
"""

import os
import numpy as np
import torch
import torch.nn as nn


MODEL_PATH = os.path.join("ai_engine", "checkpoints", "lstm_model.pth")
SEQ_LEN    = 24   # look back 24 hours
PRED_STEPS = 4    # predict next 4 hours
N_FEATURES = 4    # hour, day_of_week, is_weekend, occupancy_rate
HIDDEN_DIM = 64
N_LAYERS   = 2


# ─── PyTorch LSTM Architecture ────────────────────────────────────────────────

class OccupancyLSTM(nn.Module):
    """
    Stacked LSTM for parking occupancy time-series forecasting.
    Predicts next PRED_STEPS hours of occupancy from last SEQ_LEN hours.
    """

    def __init__(self, n_features=N_FEATURES, hidden_dim=HIDDEN_DIM,
                 n_layers=N_LAYERS, pred_steps=PRED_STEPS, dropout=0.2):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.n_layers   = n_layers
        self.pred_steps = pred_steps

        self.lstm = nn.LSTM(
            input_size=n_features,
            hidden_size=hidden_dim,
            num_layers=n_layers,
            batch_first=True,
            dropout=dropout if n_layers > 1 else 0.0,
        )
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_dim, pred_steps)

    def forward(self, x):
        # x: (batch, seq_len, n_features)
        out, _ = self.lstm(x)
        out = self.dropout(out[:, -1, :])  # take last time step
        return self.fc(out)               # (batch, pred_steps)


# ─── Data Preparation ─────────────────────────────────────────────────────────

def build_sequences(df, seq_len=SEQ_LEN, pred_steps=PRED_STEPS):
    """
    Convert hourly occupancy DataFrame into sliding-window sequences.

    df columns required: hour, day_of_week, is_weekend, occupancy_rate
    occupancy_rate: 0.0–1.0 fraction of slots occupied in that hour

    Returns:
        X: (n_samples, seq_len, n_features) float32 array
        y: (n_samples, pred_steps)          float32 array
    """
    if df.empty or len(df) < seq_len + pred_steps:
        return None, None

    features = df[["hour", "day_of_week", "is_weekend", "occupancy_rate"]].values.astype(np.float32)
    # Normalize: hour/23, day/6, is_weekend already 0/1, occupancy already 0-1
    features[:, 0] /= 23.0
    features[:, 1] /= 6.0

    targets = df["occupancy_rate"].values.astype(np.float32)

    X, y = [], []
    for i in range(len(features) - seq_len - pred_steps + 1):
        X.append(features[i : i + seq_len])
        y.append(targets[i + seq_len : i + seq_len + pred_steps])

    return np.array(X), np.array(y)


def booking_history_to_hourly(booking_df):
    """
    Aggregate booking DataFrame (from BookingHistoryDataset) into
    hourly occupancy rates — one row per hour.

    Returns a DataFrame with: hour, day_of_week, is_weekend, occupancy_rate
    """
    import pandas as pd

    if booking_df is None or booking_df.empty:
        return _generate_synthetic_hourly()

    # Count bookings per hour
    hourly = booking_df.groupby(["hour", "day_of_week"])["is_occupied"].agg(
        ["sum", "count"]
    ).reset_index()
    hourly.columns = ["hour", "day_of_week", "occupied_count", "total_count"]
    hourly["occupancy_rate"] = (hourly["occupied_count"] / hourly["total_count"].clip(lower=1)).clip(0, 1)
    hourly["is_weekend"]     = (hourly["day_of_week"] >= 5).astype(float)

    # Expand to a time series (repeat weekly pattern for 4 weeks to get enough data)
    rows = []
    for week in range(4):
        for _, row in hourly.iterrows():
            rows.append({
                "hour":          row["hour"],
                "day_of_week":   row["day_of_week"],
                "is_weekend":    row["is_weekend"],
                "occupancy_rate": row["occupancy_rate"],
            })
    result = pd.DataFrame(rows)
    # Not enough variety in real data — augment with synthetic
    if len(result) < SEQ_LEN + PRED_STEPS:
        return _generate_synthetic_hourly()
    return result


def _generate_synthetic_hourly():
    """
    Generate a realistic synthetic occupancy time series for 8 weeks.
    Follows real-world patterns: morning rush, lunch peak, evening peak.
    """
    import pandas as pd

    rows = []
    # 8 weeks = 56 days
    for day_offset in range(56):
        day_of_week = day_offset % 7
        is_weekend  = float(day_of_week >= 5)

        for hour in range(24):
            # Base occupancy pattern
            if is_weekend:
                occ = 0.15 + 0.3 * np.exp(-((hour - 12) ** 2) / 18)  # midday peak
            else:
                # Weekday: morning rush (9am), lunch (1pm), evening rush (6pm)
                morning = 0.4 * np.exp(-((hour - 9)  ** 2) / 4)
                lunch   = 0.35 * np.exp(-((hour - 13) ** 2) / 3)
                evening = 0.5 * np.exp(-((hour - 18) ** 2) / 5)
                occ = 0.05 + morning + lunch + evening

            # Add realistic noise
            noise = np.random.normal(0, 0.05)
            occ = float(np.clip(occ + noise, 0.0, 1.0))

            rows.append({
                "hour":          hour,
                "day_of_week":   day_of_week,
                "is_weekend":    is_weekend,
                "occupancy_rate": occ,
            })

    return pd.DataFrame(rows)


# ─── Trainer ──────────────────────────────────────────────────────────────────

class OccupancyForecaster:
    """
    LSTM wrapper with fit / forecast / save / load interface.
    """

    def __init__(self, seq_len=SEQ_LEN, pred_steps=PRED_STEPS,
                 hidden_dim=HIDDEN_DIM, n_layers=N_LAYERS):
        self.seq_len    = seq_len
        self.pred_steps = pred_steps
        self.device     = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model      = OccupancyLSTM(
            hidden_dim=hidden_dim,
            n_layers=n_layers,
            pred_steps=pred_steps
        ).to(self.device)
        self.train_loss_ = None
        self.val_loss_   = None

    def fit(self, hourly_df, epochs=30, lr=1e-3, batch_size=32, verbose=True):
        """
        Train the LSTM on hourly occupancy data.
        hourly_df: DataFrame with hour, day_of_week, is_weekend, occupancy_rate
        """
        from torch.utils.data import TensorDataset, DataLoader

        X, y = build_sequences(hourly_df, self.seq_len, self.pred_steps)
        if X is None:
            raise ValueError("Not enough data to build sequences. Need at least 30 hours of data.")

        # 80/20 split
        split = int(len(X) * 0.8)
        X_train, X_val = X[:split], X[split:]
        y_train, y_val = y[:split], y[split:]

        train_ds = TensorDataset(
            torch.tensor(X_train), torch.tensor(y_train)
        )
        val_ds = TensorDataset(
            torch.tensor(X_val), torch.tensor(y_val)
        )
        train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
        val_loader   = DataLoader(val_ds,   batch_size=batch_size)

        criterion = nn.MSELoss()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)

        best_val_loss = float("inf")
        for epoch in range(1, epochs + 1):
            # Train
            self.model.train()
            total_loss = 0.0
            for Xb, yb in train_loader:
                Xb, yb = Xb.to(self.device), yb.to(self.device)
                optimizer.zero_grad()
                pred = self.model(Xb)
                loss = criterion(pred, yb)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                optimizer.step()
                total_loss += loss.item()
            train_loss = total_loss / len(train_loader)

            # Validate
            self.model.eval()
            val_loss = 0.0
            with torch.no_grad():
                for Xb, yb in val_loader:
                    Xb, yb = Xb.to(self.device), yb.to(self.device)
                    val_loss += criterion(self.model(Xb), yb).item()
            val_loss /= max(len(val_loader), 1)
            scheduler.step(val_loss)

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                self._save_best()

            if verbose and (epoch % 5 == 0 or epoch == 1):
                print(f"  LSTM Epoch {epoch:02d}/{epochs} | train loss={train_loss:.4f} | val loss={val_loss:.4f}")

        self.train_loss_ = train_loss
        self.val_loss_   = best_val_loss
        return self

    def forecast(self, recent_hours_df):
        """
        Predict next PRED_STEPS hours of occupancy.

        recent_hours_df: DataFrame with last SEQ_LEN rows of
                         hour, day_of_week, is_weekend, occupancy_rate

        Returns:
            list of floats — occupancy probabilities for next 4 hours
        """
        self.model.eval()
        features = recent_hours_df[["hour", "day_of_week", "is_weekend", "occupancy_rate"]].values.astype(np.float32)
        features[:, 0] /= 23.0
        features[:, 1] /= 6.0

        x = torch.tensor(features[-self.seq_len:]).unsqueeze(0).to(self.device)
        with torch.no_grad():
            pred = self.model(x).squeeze().cpu().numpy()

        return [float(np.clip(p, 0.0, 1.0)) for p in (pred if pred.ndim > 0 else [pred])]

    def _save_best(self, path=MODEL_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        torch.save({
            "model_state_dict": self.model.state_dict(),
            "seq_len":    self.seq_len,
            "pred_steps": self.pred_steps,
        }, path)

    def save(self, path=MODEL_PATH):
        self._save_best(path)
        return path

    @classmethod
    def load(cls, path=MODEL_PATH):
        data = torch.load(path, map_location="cpu")
        obj = cls(seq_len=data["seq_len"], pred_steps=data["pred_steps"])
        obj.model.load_state_dict(data["model_state_dict"])
        obj.model.eval()
        return obj

    @classmethod
    def is_trained(cls, path=MODEL_PATH):
        return os.path.exists(path)
