"""
Management command: python manage.py train_random_forest

Trains the Random Forest model (Model 2) on Dataset 12 (booking history).
Works even with just a few dozen bookings — improves as more bookings accumulate.

Usage:
  python manage.py train_random_forest
  python manage.py train_random_forest --synthetic   # use synthetic data if DB is sparse
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Train Random Forest availability predictor on booking history (Model 2)."

    def add_arguments(self, parser):
        parser.add_argument("--synthetic", action="store_true",
                            help="Augment with synthetic bookings if real data is sparse")
        parser.add_argument("--output", default="ai_engine/checkpoints/random_forest.pkl")

    def handle(self, *args, **options):
        import numpy as np
        import pandas as pd
        from ai_engine.datasets.registry import get_dataset
        from ai_engine.ml_models.random_forest import ParkingAvailabilityRF

        self.stdout.write("\nLoading booking history (Dataset 12)...")
        ds = get_dataset("bookinghistory")
        df = ds.get_tabular_samples()

        if df is None or df.empty or (len(df) < 20 and not options["synthetic"]):
            self.stdout.write("  Not enough real bookings. Using synthetic data...")
            options["synthetic"] = True

        if options["synthetic"]:
            df = self._augment_with_synthetic(df)

        self.stdout.write(f"  Total samples: {len(df):,} | Occupied: {df['is_occupied'].sum():,}")

        # Train/val split (80/20)
        split = int(len(df) * 0.8)
        df = df.sample(frac=1, random_state=42).reset_index(drop=True)
        train_df, val_df = df.iloc[:split], df.iloc[split:]

        self.stdout.write(f"\nTraining Random Forest on {len(train_df):,} samples...")
        rf = ParkingAvailabilityRF(n_estimators=100)
        rf.fit(train_df, val_df)
        rf.save(options["output"])

        self.stdout.write(f"  Train accuracy: {rf.train_accuracy_:.1%}")
        if rf.val_accuracy_:
            self.stdout.write(f"  Val accuracy  : {rf.val_accuracy_:.1%}")

        self.stdout.write("\nTop feature importances:")
        for feat, importance in rf.top_features().items():
            bar = "#" * int(importance * 30)
            self.stdout.write(f"  {feat:15s} {bar} {importance:.3f}")

        self.stdout.write(self.style.SUCCESS(
            f"\nRandom Forest trained!\n"
            f"  Model saved: {options['output']}\n"
            f"  Usage: Predicts slot availability by hour/day/zone\n"
        ))

    def _augment_with_synthetic(self, real_df):
        """Generate synthetic booking records covering all hours and days."""
        import pandas as pd
        import numpy as np
        from parking.models import ParkingLot, ParkingZone

        rows = []
        lots  = list(ParkingLot.objects.values_list("name", flat=True)) or ["Main Lot"]
        zones = list(ParkingZone.objects.values_list("name", flat=True)) or ["Zone A", "Zone B"]

        for day in range(7):
            for hour in range(24):
                is_weekend = int(day >= 5)
                # Realistic occupancy pattern
                if is_weekend:
                    occ_prob = 0.2 + 0.4 * np.exp(-((hour - 12) ** 2) / 15)
                else:
                    morning = 0.35 * np.exp(-((hour - 9)  ** 2) / 3)
                    lunch   = 0.30 * np.exp(-((hour - 13) ** 2) / 2)
                    evening = 0.40 * np.exp(-((hour - 18) ** 2) / 4)
                    occ_prob = 0.05 + morning + lunch + evening

                for lot in lots:
                    for zone in zones:
                        for _ in range(8):  # 8 samples per slot
                            is_occ = int(np.random.random() < occ_prob)
                            rows.append({
                                "hour": hour, "day_of_week": day, "month": 1,
                                "is_weekend": is_weekend, "lot_name": lot,
                                "zone_name": zone, "status": "confirmed" if is_occ else "cancelled",
                                "is_occupied": is_occ,
                            })

        synthetic_df = pd.DataFrame(rows)
        if real_df is not None and not real_df.empty:
            return pd.concat([real_df, synthetic_df], ignore_index=True)
        return synthetic_df
