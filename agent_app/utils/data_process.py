"""
Data processing tools for time series analysis.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import os
import uuid

from models.schemas import CSVProfile, ColumnInfo, ColumnType


def load_csv_file(
    file_path: str,
    encoding: str = 'utf-8',
    delimiter: Optional[str] = None
) -> pd.DataFrame:
    """
    Load a CSV file into a DataFrame.

    Args:
        file_path: Path to the CSV file
        encoding: File encoding
        delimiter: Optional delimiter override

    Returns:
        Loaded DataFrame

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file cannot be parsed
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        # Try to detect delimiter if not specified
        if delimiter is None:
            with open(file_path, 'r', encoding=encoding) as f:
                first_line = f.readline()
                if ',' in first_line:
                    delimiter = ','
                elif ';' in first_line:
                    delimiter = ';'
                elif '\t' in first_line:
                    delimiter = '\t'
                else:
                    delimiter = ','

        df = pd.read_csv(file_path, encoding=encoding, delimiter=delimiter)
        return df

    except Exception as e:
        raise ValueError(f"Failed to load CSV file: {e}")


def analyze_column(
    df: pd.DataFrame,
    column_name: str,
    sample_size: int = 100
) -> ColumnInfo:
    """
    Analyze a single column and generate profile information.

    Args:
        df: The DataFrame containing the column
        column_name: Name of the column to analyze
        sample_size: Number of sample values to collect

    Returns:
        ColumnInfo object with column analysis
    """
    series = df[column_name]
    total_count = len(series)
    missing_count = series.isna().sum()
    missing_rate = missing_count / total_count if total_count > 0 else 0

    # Determine column type
    column_type = _detect_column_type(series)

    # Collect sample values
    sample_values = series.dropna().head(sample_size).tolist()

    # Build column info
    column_info = ColumnInfo(
        name=column_name,
        type=column_type,
        missing_rate=missing_rate,
        unique_count=series.nunique(),
        sample_values=sample_values[:10]  # Limit to 10 samples
    )

    # Add distribution statistics for numeric columns
    if column_type == ColumnType.NUMERIC:
        stats = {
            'mean': float(series.mean()) if not series.isna().all() else None,
            'std': float(series.std()) if not series.isna().all() else None,
            'min': float(series.min()) if not series.isna().all() else None,
            'max': float(series.max()) if not series.isna().all() else None,
            'median': float(series.median()) if not series.isna().all() else None,
            'q25': float(series.quantile(0.25)) if not series.isna().all() else None,
            'q75': float(series.quantile(0.75)) if not series.isna().all() else None
        }
        column_info.distribution_stats = stats

    # Detect candidate roles
    column_info.is_time_column_candidate = _is_time_column_candidate(series, column_type)
    column_info.is_target_column_candidate = _is_target_column_candidate(series, column_type)
    column_info.is_grouping_column_candidate = _is_grouping_column_candidate(series, column_type)

    # Detect anomalies
    column_info.anomaly_indicators = _detect_column_anomalies(series, column_type)

    return column_info


def _detect_column_type(series: pd.Series) -> ColumnType:
    """
    Detect the type of a column.

    Args:
        series: The series to analyze

    Returns:
        Detected ColumnType
    """
    dtype = series.dtype

    # Check for numeric types
    if pd.api.types.is_numeric_dtype(series):
        # Check if it's actually a boolean (0/1)
        if series.dropna().isin([0, 1]).all() and series.nunique() <= 2:
            return ColumnType.BOOLEAN
        return ColumnType.NUMERIC

    # Check for datetime types
    if pd.api.types.is_datetime64_any_dtype(series):
        return ColumnType.TEMPORAL

    # Check if it can be parsed as datetime
    if series.dtype == 'object':
        # Try to parse as datetime
        try:
            pd.to_datetime(series, errors='coerce')
            valid_dates = pd.to_datetime(series, errors='coerce').notna().sum()
            if valid_dates / len(series) > 0.8:  # 80% valid dates
                return ColumnType.TEMPORAL
        except:
            pass

        # Check for boolean strings
        unique_values = series.dropna().unique()
        if len(unique_values) <= 10 and all(
            str(v).lower() in ['true', 'false', 'yes', 'no', '1', '0']
            for v in unique_values
        ):
            return ColumnType.BOOLEAN

        # Check for categorical (low cardinality text)
        if series.nunique() < len(series) * 0.5:  # Less than 50% unique
            return ColumnType.CATEGORICAL

        return ColumnType.TEXT

    return ColumnType.UNKNOWN


def _is_time_column_candidate(series: pd.Series, column_type: ColumnType) -> bool:
    """Determine if column is a time column candidate."""
    if column_type == ColumnType.TEMPORAL:
        return True

    # Check for string columns that look like dates
    if column_type in [ColumnType.TEXT, ColumnType.CATEGORICAL]:
        try:
            parsed = pd.to_datetime(series, errors='coerce')
            valid_ratio = parsed.notna().sum() / len(series)
            return valid_ratio > 0.8
        except:
            pass

    return False


def _is_target_column_candidate(series: pd.Series, column_type: ColumnType) -> bool:
    """Determine if column is a target column candidate."""
    # Target columns should be numeric
    if column_type == ColumnType.NUMERIC:
        # Should have enough data points (not too many unique values for continuous,
        # not too few for discrete)
        unique_ratio = series.nunique() / len(series)
        return 0.01 < unique_ratio <= 1.0

    return False


def _is_grouping_column_candidate(series: pd.Series, column_type: ColumnType) -> bool:
    """Determine if column is a grouping column candidate."""
    # Grouping columns should be categorical or low-cardinality numeric
    if column_type == ColumnType.CATEGORICAL:
        return series.nunique() < len(series) * 0.5

    if column_type == ColumnType.NUMERIC:
        # Numeric with low cardinality could be grouping
        return series.nunique() < 50

    return False


def _detect_column_anomalies(series: pd.Series, column_type: ColumnType) -> List[str]:
    """Detect anomalies in a column."""
    anomalies = []

    # High missing rate
    missing_rate = series.isna().sum() / len(series)
    if missing_rate > 0.5:
        anomalies.append(f"High missing rate: {missing_rate:.1%}")

    # Single value (constant)
    if series.nunique() == 1:
        anomalies.append("Constant column (only one unique value)")

    # High cardinality for categorical
    if column_type == ColumnType.CATEGORICAL:
        unique_ratio = series.nunique() / len(series)
        if unique_ratio > 0.9:
            anomalies.append("High cardinality for categorical column")

    # Extreme outliers for numeric
    if column_type == ColumnType.NUMERIC:
        Q1 = series.quantile(0.25)
        Q3 = series.quantile(0.75)
        IQR = Q3 - Q1
        outliers = ((series < (Q1 - 3 * IQR)) | (series > (Q3 + 3 * IQR))).sum()
        if outliers > len(series) * 0.05:  # More than 5% extreme outliers
            anomalies.append(f"High number of outliers: {outliers}")

    return anomalies


def detect_time_column(df: pd.DataFrame, column_infos: Dict[str, ColumnInfo]) -> Optional[str]:
    """
    Detect the most likely time column in the DataFrame.

    Args:
        df: The DataFrame to analyze
        column_infos: Dictionary of column information

    Returns:
        Name of the detected time column, or None if not found
    """
    time_candidates = [
        name for name, info in column_infos.items()
        if info.is_time_column_candidate
    ]

    if not time_candidates:
        return None

    # Prefer columns with 'time', 'date', 'timestamp' in name
    preferred_keywords = ['time', 'date', 'timestamp']
    for keyword in preferred_keywords:
        for candidate in time_candidates:
            if keyword in candidate.lower():
                return candidate

    # Return first candidate
    return time_candidates[0] if time_candidates else None


def detect_target_column(df: pd.DataFrame, column_infos: Dict[str, ColumnInfo]) -> Optional[str]:
    """
    Detect the most likely target column in the DataFrame.

    Args:
        df: The DataFrame to analyze
        column_infos: Dictionary of column information

    Returns:
        Name of the detected target column, or None if not found
    """
    target_candidates = [
        name for name, info in column_infos.items()
        if info.is_target_column_candidate
    ]

    if not target_candidates:
        return None

    # Prefer columns with 'value', 'target', 'output', 'y' in name
    preferred_keywords = ['value', 'target', 'output', 'y', 'result', 'sales']
    for keyword in preferred_keywords:
        for candidate in target_candidates:
            if keyword in candidate.lower():
                return candidate

    # Return first candidate
    return target_candidates[0] if target_candidates else None


def calculate_correlations(
    df: pd.DataFrame,
    numeric_columns: List[str],
    method: str = 'pearson'
) -> Dict[str, Dict[str, float]]:
    """
    Calculate correlations between numeric columns.

    Args:
        df: The DataFrame
        numeric_columns: List of numeric column names
        method: Correlation method ('pearson', 'spearman', 'kendall')

    Returns:
        Dictionary of correlations
    """
    if len(numeric_columns) < 2:
        return {}

    try:
        corr_matrix = df[numeric_columns].corr(method=method)

        # Convert to dictionary
        correlations = {}
        for i, col1 in enumerate(numeric_columns):
            correlations[col1] = {}
            for j, col2 in enumerate(numeric_columns):
                if i != j:  # Skip diagonal
                    correlations[col1][col2] = float(corr_matrix.loc[col1, col2])

        return correlations

    except Exception as e:
        print(f"Error calculating correlations: {e}")
        return {}


def generate_csv_profile(
    file_path: str,
    file_name: Optional[str] = None
) -> CSVProfile:
    """
    Generate a comprehensive profile for a CSV file.

    Args:
        file_path: Path to the CSV file
        file_name: Optional file name (defaults to basename of path)

    Returns:
        CSVProfile object
    """
    # Load the file
    df = load_csv_file(file_path)

    # Generate file name if not provided
    if file_name is None:
        file_name = os.path.basename(file_path)

    # Analyze all columns
    columns = {}
    for column_name in df.columns:
        columns[column_name] = analyze_column(df, column_name)

    # Detect time and target columns
    time_column = detect_time_column(df, columns)
    target_column = detect_target_column(df, columns)

    # Categorize columns
    numeric_columns = [
        name for name, info in columns.items()
        if info.type == ColumnType.NUMERIC
    ]
    categorical_columns = [
        name for name, info in columns.items()
        if info.type == ColumnType.CATEGORICAL
    ]
    text_columns = [
        name for name, info in columns.items()
        if info.type == ColumnType.TEXT
    ]

    # Detect grouping columns
    grouping_columns = [
        name for name, info in columns.items()
        if info.is_grouping_column_candidate
    ]

    # Calculate correlations for numeric columns
    correlations = calculate_correlations(df, numeric_columns) if numeric_columns else None

    # Detect initial anomalies
    initial_anomalies = []
    for name, info in columns.items():
        if info.anomaly_indicators:
            initial_anomalies.append(f"{name}: {', '.join(info.anomaly_indicators)}")

    # Guess business domain
    business_domain = guess_business_domain(df, columns)

    # Build profile
    profile = CSVProfile(
        file_name=file_name,
        file_path=file_path,
        dataset_id=str(uuid.uuid4()),
        total_rows=len(df),
        total_columns=len(df.columns),
        columns=columns,
        time_column_candidates=[time_column] if time_column else [],
        target_column_candidates=[target_column] if target_column else [],
        grouping_columns=grouping_columns,
        numeric_columns=numeric_columns,
        categorical_columns=categorical_columns,
        text_columns=text_columns,
        correlation_overview=correlations,
        initial_anomaly_detection=initial_anomalies,
        business_domain_guess=business_domain
    )

    return profile


def guess_business_domain(df: pd.DataFrame, columns: Dict[str, ColumnInfo]) -> Optional[str]:
    """
    Guess the business domain based on column names and data characteristics.

    Args:
        df: The DataFrame
        columns: Column information

    Returns:
        Guessed business domain or None
    """
    column_names_lower = [name.lower() for name in df.columns]

    # Industrial/manufacturing domain
    if any(keyword in ' '.join(column_names_lower) for keyword in
           ['sensor', 'temperature', 'pressure', 'vibration', 'machine', 'equipment']):
        return 'Industrial/Manufacturing'

    # Financial domain
    if any(keyword in ' '.join(column_names_lower) for keyword in
           ['price', 'stock', 'revenue', 'sales', 'profit', 'financial', 'trading']):
        return 'Financial'

    # Retail domain
    if any(keyword in ' '.join(column_names_lower) for keyword in
           ['product', 'customer', 'inventory', 'retail', 'store', 'sales']):
        return 'Retail'

    # Energy domain
    if any(keyword in ' '.join(column_names_lower) for keyword in
           ['energy', 'power', 'consumption', 'electricity', 'wind', 'solar']):
        return 'Energy'

    # IoT domain
    if any(keyword in ' '.join(column_names_lower) for keyword in
           ['iot', 'device', 'sensor', 'measurement', 'metric']):
        return 'IoT'

    return None


def validate_data_for_task(
    df: pd.DataFrame,
    task_type: str,
    target_column: Optional[str] = None,
    time_column: Optional[str] = None
) -> Tuple[bool, List[str]]:
    """
    Validate data for a specific task type.

    Args:
        df: The DataFrame to validate
        task_type: Type of task ('prediction', 'anomaly_detection', etc.)
        target_column: Optional target column name
        time_column: Optional time column name

    Returns:
        Tuple of (is_valid, list of validation errors/warnings)
    """
    errors = []
    warnings = []

    if df.empty:
        errors.append("DataFrame is empty")
        return False, errors

    # Check for sufficient data
    if len(df) < 10:
        warnings.append("Dataset has very few rows (< 10)")

    # Task-specific validation
    if task_type == 'prediction':
        if not target_column:
            errors.append("Target column required for prediction")
        if not time_column:
            errors.append("Time column required for prediction")

        if target_column and target_column not in df.columns:
            errors.append(f"Target column '{target_column}' not found")
        if time_column and time_column not in df.columns:
            errors.append(f"Time column '{time_column}' not found")

    elif task_type == 'anomaly_detection':
        if not target_column:
            errors.append("Target column required for anomaly detection")

        if target_column and target_column not in df.columns:
            errors.append(f"Target column '{target_column}' not found")

    return len(errors) == 0, errors + warnings
