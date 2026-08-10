"""
Generate test data for the Industrial Time Series Agent System.

This script creates sample CSV files for testing various analysis scenarios.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os


def create_sample_sensor_data(rows=1000, filename='data/sensor_data.csv'):
    """Create sample sensor data with trends and anomalies."""
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    # Generate time series
    start_date = datetime(2024, 1, 1)
    dates = [start_date + timedelta(hours=i) for i in range(rows)]

    # Generate base signal with trend and seasonality
    t = np.arange(rows)
    trend = 0.05 * t
    seasonality = 10 * np.sin(2 * np.pi * t / 24)  # Daily seasonality
    noise = np.random.normal(0, 2, rows)
    signal = 50 + trend + seasonality + noise

    # Add some anomalies
    anomaly_indices = np.random.choice(rows, size=int(rows * 0.05), replace=False)
    signal[anomaly_indices] += np.random.choice([20, -20], size=len(anomaly_indices))

    # Create DataFrame
    df = pd.DataFrame({
        'timestamp': dates,
        'temperature': signal,
        'pressure': signal * 1.2 + np.random.normal(0, 1, rows),
        'vibration': np.abs(np.random.normal(5, 1, rows)),
        'machine_id': np.random.choice(['M001', 'M002', 'M003'], rows),
        'status': np.random.choice(['normal', 'warning', 'error'], rows, p=[0.9, 0.08, 0.02])
    })

    df.to_csv(filename, index=False)
    print(f"Created sensor data: {filename}")
    return df


def create_sample_sales_data(rows=365, filename='data/sales_data.csv'):
    """Create sample sales data with seasonal patterns."""
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    # Generate daily data for a year
    start_date = datetime(2024, 1, 1)
    dates = [start_date + timedelta(days=i) for i in range(rows)]

    # Generate sales with weekly and seasonal patterns
    t = np.arange(rows)
    weekly_pattern = 20 * np.sin(2 * np.pi * t / 7)
    seasonal_pattern = 30 * np.sin(2 * np.pi * t / 365)
    trend = 0.1 * t
    noise = np.random.normal(0, 5, rows)
    sales = 100 + weekly_pattern + seasonal_pattern + trend + noise

    # Ensure no negative sales
    sales = np.maximum(sales, 10)

    # Create DataFrame
    df = pd.DataFrame({
        'date': dates,
        'sales': sales,
        'revenue': sales * np.random.uniform(10, 20, rows),
        'customers': np.random.poisson(50, rows),
        'product_category': np.random.choice(['Electronics', 'Clothing', 'Food'], rows),
        'store_id': np.random.choice(['S001', 'S002', 'S003', 'S004'], rows),
        'promotion': np.random.choice([0, 1], rows, p=[0.8, 0.2])
    })

    df.to_csv(filename, index=False)
    print(f"Created sales data: {filename}")
    return df


def create_sample_industrial_data(rows=500, filename='data/industrial_data.csv'):
    """Create sample industrial data with multiple variables."""
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    # Generate time series
    start_date = datetime(2024, 1, 1)
    dates = [start_date + timedelta(minutes=30*i) for i in range(rows)]

    # Generate correlated industrial variables
    base_signal = 50 + 10 * np.sin(np.arange(rows) / 50) + np.random.normal(0, 2, rows)

    # Create DataFrame with multiple measurements
    df = pd.DataFrame({
        'timestamp': dates,
        'temperature': base_signal + np.random.normal(0, 1, rows),
        'pressure': base_signal * 1.5 + np.random.normal(0, 3, rows),
        'flow_rate': base_signal * 0.8 + np.random.normal(0, 1.5, rows),
        'quality_index': np.random.uniform(80, 100, rows),
        'production_count': np.random.poisson(100, rows),
        'equipment_id': np.random.choice(['EQ001', 'EQ002', 'EQ003', 'EQ004'], rows),
        'shift': np.random.choice(['Morning', 'Afternoon', 'Night'], rows),
        'operator_id': np.random.choice(['OP001', 'OP002', 'OP003', 'OP004', 'OP005'], rows),
        'maintenance_flag': np.random.choice([0, 1], rows, p=[0.95, 0.05])
    })

    # Add some quality issues
    quality_issue_indices = np.random.choice(rows, size=int(rows * 0.03), replace=False)
    df.loc[quality_issue_indices, 'quality_index'] = np.random.uniform(60, 79, len(quality_issue_indices))

    df.to_csv(filename, index=False)
    print(f"Created industrial data: {filename}")
    return df


def create_sample_financial_data(rows=252, filename='data/financial_data.csv'):
    """Create sample financial data (trading days)."""
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    # Generate trading days (approximately 252 days per year)
    start_date = datetime(2024, 1, 1)
    dates = []
    current_date = start_date
    while len(dates) < rows:
        if current_date.weekday() < 5:  # Monday to Friday
            dates.append(current_date)
        current_date += timedelta(days=1)

    # Generate stock-like price movements
    returns = np.random.normal(0.0005, 0.02, rows)  # Daily returns
    prices = [100]
    for ret in returns[1:]:
        prices.append(prices[-1] * (1 + ret))

    # Create DataFrame
    df = pd.DataFrame({
        'date': dates,
        'open': prices,
        'high': [p * (1 + abs(np.random.normal(0, 0.01))) for p in prices],
        'low': [p * (1 - abs(np.random.normal(0, 0.01))) for p in prices],
        'close': [p * (1 + np.random.normal(0, 0.005)) for p in prices],
        'volume': np.random.randint(1000000, 10000000, rows),
        'ticker': np.random.choice(['AAPL', 'GOOGL', 'MSFT', 'AMZN'], rows),
        'sector': np.random.choice(['Technology', 'Finance', 'Healthcare'], rows)
    })

    df.to_csv(filename, index=False)
    print(f"Created financial data: {filename}")
    return df


def create_simple_test_data(filename='data/test_data.csv'):
    """Create simple test data for basic functionality."""
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    # Very simple predictable data
    df = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=100),
        'value': range(100, 200),  # Linear trend
        'category': ['A', 'B', 'C'] * 33 + ['A']
    })

    df.to_csv(filename, index=False)
    print(f"Created simple test data: {filename}")
    return df


def main():
    """Generate all test datasets."""
    print("=" * 60)
    print("生成测试数据集")
    print("=" * 60)
    print()

    try:
        # Generate all datasets
        create_simple_test_data()
        create_sample_sensor_data()
        create_sample_sales_data()
        create_sample_industrial_data()
        create_sample_financial_data()

        print()
        print("=" * 60)
        print("✅ 所有测试数据集生成完成！")
        print("=" * 60)
        print()
        print("生成的文件:")
        print("  - data/test_data.csv (简单测试数据)")
        print("  - data/sensor_data.csv (传感器数据)")
        print("  - data/sales_data.csv (销售数据)")
        print("  - data/industrial_data.csv (工业数据)")
        print("  - data/financial_data.csv (金融数据)")
        print()

    except Exception as e:
        print(f"❌ 生成数据时出错: {str(e)}")


if __name__ == '__main__':
    main()
