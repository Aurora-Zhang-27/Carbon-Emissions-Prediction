import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout

# 1. Load the energy, weather, and historical carbon emission data
energy_data_path = '/Users/mac/Desktop/CAISO2/PJM 5 minute standardized data_2024-09-30T00_00_00-04_00_2024-10-30T23_59_59.999000-04_00.csv'  # Replace with actual file path
weather_data_path = '/Users/mac/Desktop/CAISO2/new york 2024-09-30 to 2024-10-30.csv'  # Replace with actual file path
historical_emissions_path = '/Users/mac/Desktop/CAISO2/hourly_emission_rates.csv'  # Replace with actual file path

energy_data = pd.read_csv(energy_data_path)
weather_data = pd.read_csv(weather_data_path)
historical_emissions = pd.read_csv(historical_emissions_path)

# 2. Preprocess data
energy_data['datetime'] = pd.to_datetime(energy_data['interval_start_utc']).dt.tz_localize(None)  # Replace 'interval_start_utc' with actual column name
weather_data['datetime'] = pd.to_datetime(weather_data['datetime']).dt.tz_localize(None)  # Replace 'datetime' with actual column name
historical_emissions['datetime'] = pd.to_datetime(historical_emissions['datetime_beginning_utc']).dt.tz_localize(None)  # Replace 'datetime_beginning_utc' with actual column name

energy_data.set_index('datetime', inplace=True)
weather_data.set_index('datetime', inplace=True)
historical_emissions.set_index('datetime', inplace=True)

# 3. Merge energy and weather data
combined_data = pd.merge(energy_data, weather_data, left_index=True, right_index=True)

# 4. Estimate emission factors
def estimate_emission_factors(historical_emissions, combined_data):
    """Calculate emission factors for each energy type based on historical emissions data."""
    total_emission = historical_emissions['total_sum_co2'].sum()  # Total emissions
    factors = {}
    for col in combined_data.columns:
        # Calculate each energy's emission factor
        factors[col] = combined_data[col].sum() / total_emission
    return factors

# Ensure all columns in combined_data are numeric
combined_data = combined_data.apply(pd.to_numeric, errors='coerce').fillna(0)

emission_factors = estimate_emission_factors(historical_emissions, combined_data)

# 5. Calculate carbon intensity
combined_data['carbon_intensity'] = combined_data.apply(
    lambda row: sum(row[col] * emission_factors[col] for col in combined_data.columns), axis=1)

# 6. Scale the data
scaler = MinMaxScaler()
scaled_data = scaler.fit_transform(combined_data)

# 7. Build an LSTM model for time series forecasting
def build_lstm_model(input_shape):
    model = Sequential()
    model.add(LSTM(50, return_sequences=True, input_shape=input_shape))
    model.add(Dropout(0.2))
    model.add(LSTM(50, return_sequences=False))
    model.add(Dropout(0.2))
    model.add(Dense(25))
    model.add(Dense(1))
    model.compile(optimizer='adam', loss='mean_squared_error')
    return model

# 8. Prepare the training data
sequence_length = 24  # Forecast window is 24 hours
X, y = [], []
for i in range(sequence_length, len(scaled_data)):
    X.append(scaled_data[i-sequence_length:i])
    y.append(scaled_data[i, -1])  # Use carbon intensity as target

X, y = np.array(X), np.array(y)

# 9. Train the model
model = build_lstm_model((X.shape[1], X.shape[2]))
model.fit(X, y, epochs=50, batch_size=32, validation_split=0.1)

# 10. Forecast the next 24 hours of carbon emissions
last_sequence = scaled_data[-sequence_length:]
forecast = []

for _ in range(24):
    X_pred = last_sequence.reshape((1, sequence_length, last_sequence.shape[1]))
    pred = model.predict(X_pred)
    forecast.append(pred[0, 0])  # Store the scalar value for the forecast

    # Create a new row with the same number of columns as `last_sequence`
    new_row = np.zeros((1, last_sequence.shape[1]))  # Initialize with zeros
    new_row[0, 0] = pred[0, 0]  # Place the prediction in the first position

    # Append the new row to last_sequence, ensuring dimensions match
    last_sequence = np.append(last_sequence[1:], new_row, axis=0)

# Inverse scale the forecast result
forecast_array = np.zeros((24, scaled_data.shape[1]))
forecast_array[:, -1] = forecast
forecast_emission = scaler.inverse_transform(forecast_array)[:, -1]

# Visualization
# 11. Visualize the actual and predicted results
# Extract past 24 hours of actual carbon intensity data
past_24_hours = combined_data['carbon_intensity'][-24:]  # Assumes 'carbon_intensity' is computed in the previous steps

# Create time ranges
past_dates = pd.date_range(end=combined_data.index[-1], periods=24, freq='h')
future_dates = pd.date_range(start=past_dates[-1] + pd.Timedelta(hours=1), periods=24, freq='h')

# Plot the data
plt.figure(figsize=(14, 7))
plt.plot(past_dates, past_24_hours, color='blue', label='Actual Carbon Intensity (Last 24 hours)')
plt.plot(future_dates, forecast_emission, color='red', marker='o', linestyle='--', label='Predicted Carbon Emission (Next 24 hours)')

# Add titles and labels
plt.title("Past 24 Hours and Forecasted Next 24 Hours Carbon Emission")
plt.xlabel("Time")
plt.ylabel("Carbon Emission (e.g., mTCO₂/h)")
plt.legend()
plt.grid(True)
plt.xticks(rotation=45)
plt.tight_layout()

# Show the plot
plt.show()