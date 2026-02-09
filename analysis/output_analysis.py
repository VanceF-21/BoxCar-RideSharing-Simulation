"""
This module provides tools for analyzing simulation results, including confidence intervals, comparison of scenarios, and visualization preparation.
"""

import math
from typing import List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class ConfidenceInterval:
    """Confidence interval result"""
    mean: float
    lower: float
    upper: float
    std_error: float
    confidence_level: float


class OutputAnalyzer:
    """
    Analyzes simulation output data.

    Provides statistical analysis including:
    - Point estimates with confidence intervals
    - Comparison between scenarios
    - Trend analysis
    """

    def __init__(self):
        self.results: List[Dict] = []

    def add_replication(self, stats: Dict):
        """Add results from one replication"""
        self.results.append(stats)

    def calculate_confidence_interval(self, values: List[float],
                                       confidence: float = 0.95) -> ConfidenceInterval:
        """
        Calculate confidence interval for a metric.

        Uses t-distribution for small samples.

        Args:
            values: List of values from replications
            confidence: Confidence level (default 0.95)

        Returns:
            ConfidenceInterval object
        """
        n = len(values)
        if n < 2:
            mean = values[0] if values else 0
            return ConfidenceInterval(mean, mean, mean, 0, confidence)

        mean = sum(values) / n
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        std_error = math.sqrt(variance / n)

        # t-critical values for common confidence levels
        t_critical = {
            0.90: {5: 2.015, 10: 1.833, 20: 1.729, 30: 1.699},
            0.95: {5: 2.571, 10: 2.262, 20: 2.093, 30: 2.045},
            0.99: {5: 4.032, 10: 3.250, 20: 2.861, 30: 2.756}
        }

        # Get approximate t-value
        df = n - 1
        if df <= 5:
            t = t_critical.get(confidence, {}).get(5, 2.571)
        elif df <= 10:
            t = t_critical.get(confidence, {}).get(10, 2.262)
        elif df <= 20:
            t = t_critical.get(confidence, {}).get(20, 2.093)
        else:
            t = t_critical.get(confidence, {}).get(30, 2.045)

        margin = t * std_error

        return ConfidenceInterval(
            mean=mean,
            lower=mean - margin,
            upper=mean + margin,
            std_error=std_error,
            confidence_level=confidence
        )

    def compare_scenarios(self, scenario1_values: List[float],
                          scenario2_values: List[float],
                          confidence: float = 0.95) -> Dict:
        """
        Compare two scenarios using paired comparison or independent samples.

        Args:
            scenario1_values: Metric values from scenario 1
            scenario2_values: Metric values from scenario 2
            confidence: Confidence level

        Returns:
            Dictionary with comparison results
        """
        n1 = len(scenario1_values)
        n2 = len(scenario2_values)

        mean1 = sum(scenario1_values) / n1 if n1 > 0 else 0
        mean2 = sum(scenario2_values) / n2 if n2 > 0 else 0

        var1 = sum((x - mean1) ** 2 for x in scenario1_values) / (n1 - 1) if n1 > 1 else 0
        var2 = sum((x - mean2) ** 2 for x in scenario2_values) / (n2 - 1) if n2 > 1 else 0

        # Pooled standard error (assuming independent samples)
        se_diff = math.sqrt(var1 / n1 + var2 / n2) if n1 > 0 and n2 > 0 else 0

        diff = mean1 - mean2
        pct_change = (diff / mean2 * 100) if mean2 != 0 else 0

        # Approximate CI for difference
        t = 2.0  # Approximate t-value
        margin = t * se_diff

        return {
            'mean_scenario1': mean1,
            'mean_scenario2': mean2,
            'difference': diff,
            'percent_change': pct_change,
            'ci_lower': diff - margin,
            'ci_upper': diff + margin,
            'significant': abs(diff) > margin  # Rough test
        }

    def get_summary_statistics(self, metric_name: str) -> Dict:
        """
        Get summary statistics for a specific metric across replications.

        Args:
            metric_name: Name of the metric to analyze

        Returns:
            Dictionary with summary statistics
        """
        values = []
        for result in self.results:
            if metric_name in result:
                values.append(result[metric_name])

        if not values:
            return {'error': f'No data for metric: {metric_name}'}

        ci = self.calculate_confidence_interval(values)

        return {
            'metric': metric_name,
            'n_replications': len(values),
            'mean': ci.mean,
            'ci_lower': ci.lower,
            'ci_upper': ci.upper,
            'std_error': ci.std_error,
            'min': min(values),
            'max': max(values),
            'range': max(values) - min(values)
        }

    def analyze_warmup(self, time_series: List[Tuple[float, float]],
                       window_size: int = 10) -> Dict:
        """
        Analyze time series to detect warmup period.

        Uses MSER (Marginal Standard Error Rules) approach.

        Args:
            time_series: List of (time, value) tuples
            window_size: Window size for moving average

        Returns:
            Dictionary with warmup analysis results
        """
        if len(time_series) < window_size * 2:
            return {'suggested_warmup': 0, 'note': 'Insufficient data'}

        values = [v for _, v in time_series]
        times = [t for t, _ in time_series]

        # Calculate moving averages
        moving_avgs = []
        for i in range(len(values) - window_size + 1):
            window = values[i:i + window_size]
            moving_avgs.append(sum(window) / window_size)

        # Find point where moving average stabilizes
        # (variance of remaining data is minimized)
        best_cutoff = 0
        min_variance = float('inf')

        for cutoff in range(len(moving_avgs) // 2):
            remaining = moving_avgs[cutoff:]
            if len(remaining) < 2:
                continue
            mean = sum(remaining) / len(remaining)
            variance = sum((x - mean) ** 2 for x in remaining) / len(remaining)
            if variance < min_variance:
                min_variance = variance
                best_cutoff = cutoff

        # Map back to time
        warmup_time = times[best_cutoff] if best_cutoff < len(times) else 0

        return {
            'suggested_warmup': warmup_time,
            'cutoff_index': best_cutoff,
            'stabilized_mean': sum(moving_avgs[best_cutoff:]) / len(moving_avgs[best_cutoff:])
                              if best_cutoff < len(moving_avgs) else 0
        }

    def generate_latex_table(self, metrics: List[str],
                             scenario_names: List[str] = None) -> str:
        """
        Generate LaTeX table code for results.

        Args:
            metrics: List of metric names to include
            scenario_names: Names for each scenario (if multiple)

        Returns:
            LaTeX table code as string
        """
        lines = []
        lines.append(r"\begin{table}[htbp]")
        lines.append(r"\centering")
        lines.append(r"\caption{Simulation Results Summary}")
        lines.append(r"\label{tab:results}")
        lines.append(r"\begin{tabular}{lcccc}")
        lines.append(r"\toprule")
        lines.append(r"Metric & Mean & 95\% CI Lower & 95\% CI Upper & Std Error \\")
        lines.append(r"\midrule")

        for metric in metrics:
            stats = self.get_summary_statistics(metric)
            if 'error' not in stats:
                lines.append(
                    f"{metric} & {stats['mean']:.4f} & {stats['ci_lower']:.4f} & "
                    f"{stats['ci_upper']:.4f} & {stats['std_error']:.4f} \\\\"
                )

        lines.append(r"\bottomrule")
        lines.append(r"\end{tabular}")
        lines.append(r"\end{table}")

        return "\n".join(lines)

    def prepare_plot_data(self, metric_name: str) -> Dict:
        """
        Prepare data for plotting.

        Args:
            metric_name: Name of the metric

        Returns:
            Dictionary with data ready for matplotlib
        """
        values = []
        for result in self.results:
            if metric_name in result:
                values.append(result[metric_name])

        if not values:
            return {}

        ci = self.calculate_confidence_interval(values)

        return {
            'values': values,
            'mean': ci.mean,
            'ci_lower': ci.lower,
            'ci_upper': ci.upper,
            'n': len(values)
        }


def analyze_replications(stats_list: List) -> Dict:
    """
    Convenience function to analyze multiple replication results.

    Args:
        stats_list: List of SimulationStatistics objects

    Returns:
        Dictionary with comprehensive analysis
    """
    analyzer = OutputAnalyzer()

    # Extract key metrics from each replication
    for stats in stats_list:
        summary = stats.get_summary()
        analyzer.add_replication({
            'abandonment_rate': summary['rider_metrics']['abandonment_rate'],
            'avg_waiting_time': summary['rider_metrics']['average_waiting_time'],
            'avg_hourly_earnings': summary['driver_metrics']['average_hourly_earnings'],
            'gini_coefficient': summary['driver_metrics']['earnings_distribution']['gini'],
            'avg_utilization': summary['driver_metrics']['average_utilization'],
            'total_revenue': summary['system_metrics']['total_revenue'],
        })

    # Generate analysis for each metric
    metrics = ['abandonment_rate', 'avg_waiting_time', 'avg_hourly_earnings',
               'gini_coefficient', 'avg_utilization', 'total_revenue']

    results = {}
    for metric in metrics:
        results[metric] = analyzer.get_summary_statistics(metric)

    return results
