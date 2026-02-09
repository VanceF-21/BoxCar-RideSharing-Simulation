"""
This module loads all parameters from config.json and provides
a clean interface for accessing configuration values.

Supports two modes:
  - baseline:    All parameters from BoxCar PDF assumptions (distributions as specified)
  - data_driven: Analyze real data files to estimate/update key parameters
"""

import json
import os
from dataclasses import dataclass, field
from typing import Dict, Optional, Any


# Default config file path
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')


def load_json_config(config_path: str = CONFIG_FILE) -> dict:
    """Load configuration from JSON file"""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def deep_merge(base: dict, override: dict) -> dict:
    """
    Deep merge two dictionaries.
    Values in override take precedence over base.
    """
    result = base.copy()
    for key, value in override.items():
        if key.startswith('_'):  # Skip comment fields
            continue
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


@dataclass
class Config:
    """
    Unified configuration class.

    Supports two modes:
      - 'baseline': all parameters from PDF-specified distributions
      - 'data_driven': parameters estimated from real data files

    Usage:
        cfg = Config(scenario='baseline')    # PDF assumptions only
        cfg = Config(scenario='data_driven') # auto-estimate from data
    """
    # Simulation settings
    simulation_time: float = 168.0
    warmup_time: float = 24.0
    random_seed: Optional[int] = 42
    verbose: bool = False

    # Map settings
    map_size: float = 20.0

    # Driver parameters
    driver_arrival_rate: float = 3.0
    driver_availability_min: float = 5.0
    driver_availability_max: float = 8.0

    # Rider parameters
    rider_arrival_rate: float = 30.0
    rider_patience_rate: float = 5.0

    # Trip parameters
    avg_speed: float = 20.0
    trip_time_variation: float = 0.2

    # Fare parameters
    base_fare: float = 3.0
    per_mile_rate: float = 2.0
    petrol_cost_per_mile: float = 0.20

    # Data file paths
    driver_data: str = './data/drivers.xlsx'
    rider_data: str = './data/riders.xlsx'

    # Output settings
    output_directory: str = './output'
    log_file: Optional[str] = None

    # Mode and scenario
    mode: str = 'baseline'  # 'baseline' or 'data_driven'
    scenario_name: str = 'baseline'

    # Data-driven estimation results (populated at runtime)
    data_estimates: Optional[Dict] = None
    data_comparison: Optional[Dict] = None

    def __init__(self, config_path: str = CONFIG_FILE, scenario: str = None):
        """
        Initialize configuration.

        Args:
            config_path: Path to config.json file
            scenario: Scenario name to load (optional)
        """
        try:
            json_config = load_json_config(config_path)
        except FileNotFoundError:
            json_config = {}

        self._config_dir = os.path.dirname(os.path.abspath(config_path))

        # Step 1: Load baseline parameters (always start from PDF assumptions)
        self._load_baseline(json_config)

        # Step 2: Load simulation settings
        self._load_simulation_settings(json_config)

        # Step 3: Determine mode based on scenario
        scenario = scenario or json_config.get('mode', 'baseline')
        self.scenario_name = scenario

        if scenario == 'data_driven':
            # Mode 2: Estimate parameters from real data and update
            self.mode = 'data_driven'
            self._load_data_driven(json_config)
        elif scenario == 'baseline':
            # Mode 1: Pure PDF assumptions (already loaded)
            self.mode = 'baseline'
        else:
            # Other scenarios: start from baseline, then apply overrides
            self.mode = 'baseline'
            self._apply_scenario_overrides(json_config, scenario)

    def _load_baseline(self, config: dict):
        """Load baseline parameters from PDF assumptions"""
        baseline = config.get('baseline_params', {})

        # Driver parameters
        driver = baseline.get('driver', {})
        self.driver_arrival_rate = driver.get('arrival_rate', 3.0)
        self.driver_availability_min = driver.get('availability_min', 5.0)
        self.driver_availability_max = driver.get('availability_max', 8.0)

        # Rider parameters
        rider = baseline.get('rider', {})
        self.rider_arrival_rate = rider.get('arrival_rate', 30.0)
        self.rider_patience_rate = rider.get('patience_rate', 5.0)

        # Trip parameters
        trip = baseline.get('trip', {})
        self.avg_speed = trip.get('avg_speed', 20.0)
        self.trip_time_variation = trip.get('time_variation', 0.2)

        # Fare parameters
        fare = baseline.get('fare', {})
        self.base_fare = fare.get('base_fare', 3.0)
        self.per_mile_rate = fare.get('per_mile_rate', 2.0)
        self.petrol_cost_per_mile = fare.get('petrol_cost_per_mile', 0.20)

    def _load_simulation_settings(self, config: dict):
        """Load simulation and map settings"""
        sim = config.get('simulation', {})
        self.simulation_time = sim.get('simulation_time', 168.0)
        self.warmup_time = sim.get('warmup_time', 24.0)
        self.random_seed = sim.get('random_seed', 42)
        self.verbose = sim.get('verbose', False)

        map_cfg = config.get('map', {})
        self.map_size = map_cfg.get('size', 20.0)

        output = config.get('output', {})
        self.output_directory = output.get('directory', './output')
        self.log_file = output.get('log_file', None)

    def _load_data_driven(self, config: dict):
        """
        Mode 2: Analyze real data files and update parameters.

        Reads drivers.xlsx and riders.xlsx, estimates distribution parameters,
        and overrides the baseline values for specified fields.
        """
        dd_config = config.get('data_driven_params', {})
        data_files = dd_config.get('data_files', {})

        # Resolve data file paths relative to config directory
        self.driver_data = data_files.get('driver_data', './data/drivers.xlsx')
        self.rider_data = data_files.get('rider_data', './data/riders.xlsx')

        driver_path = os.path.join(self._config_dir, self.driver_data)
        rider_path = os.path.join(self._config_dir, self.rider_data)

        # Which fields to update from data
        update_fields = dd_config.get('update_fields', [
            'driver_arrival_rate',
            'driver_availability_min',
            'driver_availability_max',
            'rider_arrival_rate',
            'avg_speed'
        ])

        # Run data analysis
        try:
            from analysis.data_analysis import DataAnalyzer

            analyzer = DataAnalyzer()
            analyzer.load_data(driver_path, rider_path)
            analyzer.analyze_drivers()
            analyzer.analyze_riders()

            estimated = analyzer.get_estimated_parameters()
            comparison = analyzer.compare_with_assumptions()

            self.data_estimates = estimated
            self.data_comparison = comparison

            # Update only the specified fields
            field_mapping = {
                'driver_arrival_rate': 'driver_arrival_rate',
                'driver_availability_min': 'driver_availability_min',
                'driver_availability_max': 'driver_availability_max',
                'rider_arrival_rate': 'rider_arrival_rate',
                'avg_speed': 'avg_speed',
            }

            for field_name in update_fields:
                if field_name in field_mapping and field_name in estimated:
                    value = estimated[field_name]
                    if value is not None and value > 0:
                        setattr(self, field_mapping[field_name], value)

        except Exception as e:
            print(f"Warning: Could not load data for data_driven mode: {e}")
            print("Falling back to baseline parameters.")

    def _apply_scenario_overrides(self, config: dict, scenario: str):
        """Apply scenario-specific overrides on top of baseline"""
        scenarios = config.get('scenarios', {})
        if scenario not in scenarios:
            raise ValueError(f"Unknown scenario: {scenario}. "
                           f"Available: {list(scenarios.keys())}")

        scenario_cfg = scenarios[scenario]

        # Apply driver overrides
        if 'driver' in scenario_cfg:
            d = scenario_cfg['driver']
            if 'arrival_rate' in d:
                self.driver_arrival_rate = d['arrival_rate']
            if 'availability_min' in d:
                self.driver_availability_min = d['availability_min']
            if 'availability_max' in d:
                self.driver_availability_max = d['availability_max']

        # Apply rider overrides
        if 'rider' in scenario_cfg:
            r = scenario_cfg['rider']
            if 'arrival_rate' in r:
                self.rider_arrival_rate = r['arrival_rate']
            if 'patience_rate' in r:
                self.rider_patience_rate = r['patience_rate']

        # Apply trip overrides
        if 'trip' in scenario_cfg:
            t = scenario_cfg['trip']
            if 'avg_speed' in t:
                self.avg_speed = t['avg_speed']

        # Apply fare overrides
        if 'fare' in scenario_cfg:
            f = scenario_cfg['fare']
            if 'base_fare' in f:
                self.base_fare = f['base_fare']
            if 'per_mile_rate' in f:
                self.per_mile_rate = f['per_mile_rate']

    def to_dict(self) -> dict:
        """Convert config to dictionary (for SimulationConfig)"""
        return {
            'simulation_time': self.simulation_time,
            'warmup_time': self.warmup_time,
            'map_size': self.map_size,
            'driver_arrival_rate': self.driver_arrival_rate,
            'driver_availability_min': self.driver_availability_min,
            'driver_availability_max': self.driver_availability_max,
            'rider_arrival_rate': self.rider_arrival_rate,
            'rider_patience_rate': self.rider_patience_rate,
            'avg_speed': self.avg_speed,
            'base_fare': self.base_fare,
            'per_mile_rate': self.per_mile_rate,
            'petrol_cost_per_mile': self.petrol_cost_per_mile,
            'random_seed': self.random_seed,
            'verbose': self.verbose,
        }

    def get_mode_description(self) -> str:
        """Return a human-readable description of the current mode"""
        if self.mode == 'baseline':
            return (
                "Mode 1 - Baseline (PDF Assumptions)\n"
                "  All parameters generated from distributions specified in project spec:\n"
                f"  - Driver arrival: Exponential(rate={self.driver_arrival_rate}/hr)\n"
                f"  - Driver availability: Uniform({self.driver_availability_min}, {self.driver_availability_max}) hrs\n"
                f"  - Rider arrival: Exponential(rate={self.rider_arrival_rate}/hr)\n"
                f"  - Rider patience: Exponential(rate={self.rider_patience_rate}/hr)\n"
                f"  - Trip time: Uniform(0.8*mu, 1.2*mu), speed={self.avg_speed} mph\n"
                f"  - Fare: base={self.base_fare} + {self.per_mile_rate}/mile"
            )
        elif self.mode == 'data_driven':
            desc = (
                "Mode 2 - Data-Driven (Real Data Estimates)\n"
                "  Parameters estimated from drivers.xlsx & riders.xlsx:\n"
                f"  - Driver arrival: Exponential(rate={self.driver_arrival_rate:.2f}/hr) [from data]\n"
                f"  - Driver availability: Uniform({self.driver_availability_min:.1f}, {self.driver_availability_max:.1f}) hrs [from data]\n"
                f"  - Rider arrival: Exponential(rate={self.rider_arrival_rate:.2f}/hr) [from data]\n"
                f"  - Rider patience: Exponential(rate={self.rider_patience_rate}/hr) [baseline - no data]\n"
                f"  - Trip time: Uniform(0.8*mu, 1.2*mu), speed={self.avg_speed:.2f} mph [from data]\n"
                f"  - Fare: base={self.base_fare} + {self.per_mile_rate}/mile [baseline]"
            )
            if self.data_comparison:
                desc += "\n\n  Parameter comparison (Assumed vs Estimated):"
                for key, vals in self.data_comparison.items():
                    desc += f"\n    {key}: {vals['assumed']:.2f} -> {vals['estimated']:.2f} ({vals['difference_pct']:+.1f}%)"
            return desc
        return f"Scenario: {self.scenario_name}"

    def __repr__(self):
        return f"Config(mode='{self.mode}', scenario='{self.scenario_name}')"

    def print_summary(self):
        """Print configuration summary"""
        print(f"\n{'='*60}")
        print(self.get_mode_description())
        print(f"{'='*60}")
        print(f"Simulation: {self.simulation_time}h (warmup: {self.warmup_time}h)")
        print(f"Map size: {self.map_size} x {self.map_size} miles")
        print(f"{'='*60}\n")


def get_available_scenarios(config_path: str = CONFIG_FILE) -> list:
    """Get list of available scenario names"""
    try:
        config = load_json_config(config_path)
        return list(config.get('scenarios', {}).keys())
    except FileNotFoundError:
        return ['baseline']


# For backward compatibility - lazy SCENARIOS dict
class _LazyScenarios:
    """Lazy-loaded scenarios dict to avoid data analysis at import time"""
    def __init__(self):
        self._cache = None

    def _build(self) -> Dict[str, dict]:
        scenarios = {}
        try:
            available = get_available_scenarios()
            for name in available:
                cfg = Config(scenario=name)
                scenarios[name] = cfg.to_dict()
        except:
            scenarios['baseline'] = Config().to_dict()
        return scenarios

    def __getitem__(self, key):
        if self._cache is None:
            self._cache = self._build()
        return self._cache[key]

    def __contains__(self, key):
        if self._cache is None:
            self._cache = self._build()
        return key in self._cache

    def keys(self):
        if self._cache is None:
            self._cache = self._build()
        return self._cache.keys()

    def items(self):
        if self._cache is None:
            self._cache = self._build()
        return self._cache.items()

    def values(self):
        if self._cache is None:
            self._cache = self._build()
        return self._cache.values()


SCENARIOS = _LazyScenarios()
