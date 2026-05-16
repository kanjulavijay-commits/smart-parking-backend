"""
Management command: python manage.py train_lstm

Trains the LSTM forecasting model (Model 3) on Dataset 12.
Predicts parking occupancy for the next 4 hours based on the last 24 hours.

Uses synthetic occupancy patterns if real booking data is insufficient.

Usage:
  python manage.py train_lstm
  python manage.py train_lstm --epochs 50
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Train LSTM occupancy forecaster (Model 3) on booking time-series data."

    def add_arguments(self, parser):
        parser.add_argument("--epochs",  type=int, default=30)
        parser.add_argument("--output",  default="ai_engine/checkpoints/lstm_model.pth")

    def handle(self, *args, **options):
        from ai_engine.datasets.registry import get_dataset
        from ai_engine.ml_models.lstm_model import (
            OccupancyForecaster, booking_history_to_hourly
        )

        self.stdout.write("\nPreparing time-series data from booking history (Dataset 12)...")
        ds = get_dataset("bookinghistory")
        booking_df = ds.get_tabular_samples()
        hourly_df  = booking_history_to_hourly(booking_df)

        if booking_df is None or booking_df.empty:
            self.stdout.write("  No real data found — using synthetic occupancy patterns.")
        else:
            self.stdout.write(f"  {len(booking_df):,} bookings -> {len(hourly_df):,} hourly rows")

        self.stdout.write(f"\nTraining LSTM for {options['epochs']} epochs...")
        forecaster = OccupancyForecaster()

        try:
            forecaster.fit(hourly_df, epochs=options["epochs"], verbose=True)
        except ValueError as e:
            self.stderr.write(str(e))
            return

        forecaster.save(options["output"])

        self.stdout.write(self.style.SUCCESS(
            f"\nLSTM training complete!\n"
            f"  Final train loss : {forecaster.train_loss_:.5f}\n"
            f"  Best  val  loss  : {forecaster.val_loss_:.5f}\n"
            f"  Model saved      : {options['output']}\n\n"
            f"  Usage: Forecasts occupancy for next 4 hours\n"
            f"  Example: 'Expect 78% occupancy at 6pm today'\n"
        ))
