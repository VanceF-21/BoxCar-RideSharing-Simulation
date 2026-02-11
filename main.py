"""
BoxCar Ride-Sharing Simulation

Two input modes:
    Mode 1 (baseline): All parameters from distributions in the default BoxCar assumptions
    Mode 2 (data_driven): Estimate parameters from real data, then simulate

Usage:
    python main.py                              # Run baseline
    python main.py --scenario baseline          # baseline scenario: default BoxCar assumptions
    python main.py --scenario data_driven       # Use data-estimated parameters
    python main.py --replications 20            # Multiple replications
    python main.py --compare                    # Compare baseline vs data_driven
    python main.py --analyze-only               # Only analyze data, don't simulate
"""

import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.simulation import RideSharingSimulation, SimulationConfig
from src.matching import get_matching_algorithm
from src.logger import Logger, LogLevel, set_logger
from config import Config, get_available_scenarios
from analysis.output_analysis import analyze_replications
from analysis.data_analysis import DataAnalyzer


def parse_arguments():
    """Parse command line arguments"""
    available_scenarios = get_available_scenarios()

    parser = argparse.ArgumentParser(
        description='BoxCar Ride-Sharing Simulation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Input Modes:
  Mode 1 (baseline):    All params from distributions in the default BoxCar assumptions (exponential, uniform, etc.)
  Mode 2 (data_driven): Estimate params from real data files, update simulation

Examples:
  python main.py                           # Mode 1: baseline (default BoxCar assumptions)
  python main.py -s data_driven            # Mode 2: data-estimated parameters
  python main.py --analyze-only            # Only analyze data files
  python main.py --compare -r 5            # Compare all scenarios with 5 reps
  python main.py -s more_drivers -v        # Run scenario with verbose logging

Available scenarios: {', '.join(available_scenarios)}
        """
    )

    parser.add_argument(
        '--scenario', '-s',
        type=str,
        default='baseline',
        choices=available_scenarios,
        help='Scenario to run: baseline (default BoxCar assumptions) or data_driven (real data)'
    )

    parser.add_argument(
        '--replications', '-r',
        type=int,
        default=10,
        help='Number of replications to run (default: 10)'
    )

    parser.add_argument(
        '--time', '-t',
        type=float,
        default=None,
        help='Simulation time in hours (default: from config.json)'
    )

    parser.add_argument(
        '--matching', '-m',
        type=str,
        default='nearest',
        choices=['nearest', 'fifo', 'zoned', 'batch'],
        help='Matching algorithm to use'
    )

    parser.add_argument(
        '--analyze-only',
        action='store_true',
        help='Only analyze data files without running simulation'
    )

    parser.add_argument(
        '--compare', '-c',
        action='store_true',
        help='Run and compare all scenarios'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output (DEBUG level)'
    )

    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Minimal output (WARNING level only)'
    )

    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Output directory for results (default: from config.json)'
    )

    parser.add_argument(
        '--seed',
        type=int,
        default=None,
        help='Random seed for reproducibility (default: from config.json)'
    )

    parser.add_argument(
        '--config', '-C',
        type=str,
        default='config.json',
        help='Path to config.json file'
    )

    return parser.parse_args()


def get_output_dir_with_datetime(base_output_dir: str, mode: str = 'baseline') -> str:
    """Create date-time-stamped output subdirectory under mode folder (baseline/data_driven)"""
    datetime_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(base_output_dir, mode, f"results_{datetime_str}")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def setup_logger(output_dir: str, verbose: bool, quiet: bool, log_file: str = None) -> Logger:
    """Set up and return logger"""
    if verbose:
        console_level = LogLevel.DEBUG
    elif quiet:
        console_level = LogLevel.WARNING
    else:
        console_level = LogLevel.INFO

    os.makedirs(output_dir, exist_ok=True)

    if not log_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(output_dir, f"simulation_{timestamp}.log")

    logger = Logger(
        name="BoxCarSimulation",
        log_file=log_file,
        console_level=console_level,
        file_level=LogLevel.DEBUG,
        use_colors=True
    )

    set_logger(logger)
    return logger


def create_simulation_config(cfg: Config) -> SimulationConfig:
    """Create SimulationConfig from Config object"""
    return SimulationConfig(
        simulation_time=cfg.simulation_time,
        warmup_time=cfg.warmup_time,
        map_size=cfg.map_size,
        driver_arrival_rate=cfg.driver_arrival_rate,
        driver_availability_min=cfg.driver_availability_min,
        driver_availability_max=cfg.driver_availability_max,
        rider_arrival_rate=cfg.rider_arrival_rate,
        rider_patience_rate=cfg.rider_patience_rate,
        avg_speed=cfg.avg_speed,
        base_fare=cfg.base_fare,
        per_mile_rate=cfg.per_mile_rate,
        petrol_cost_per_mile=cfg.petrol_cost_per_mile,
        random_seed=cfg.random_seed,
        verbose=cfg.verbose
    )


def analyze_data(logger: Logger, cfg: Config) -> dict:
    """Analyze input data files"""
    logger.section("DATA ANALYSIS")

    analyzer = DataAnalyzer(logger=logger)
    analyzer.load_data(cfg.driver_data, cfg.rider_data)

    driver_results = analyzer.analyze_drivers()
    rider_results = analyzer.analyze_riders()
    comparison = analyzer.compare_with_assumptions()

    logger.subsection("Comparison with BoxCar Assumptions")
    logger.table(
        headers=['Parameter', 'Assumed', 'Estimated', 'Diff %'],
        rows=[
            [k, f"{v['assumed']:.2f}", f"{v['estimated']:.2f}", f"{v['difference_pct']:+.1f}%"]
            for k, v in comparison.items()
        ]
    )

    report = analyzer.generate_report()
    logger.info("\n" + report)

    return {
        'driver_analysis': driver_results,
        'rider_analysis': rider_results,
        'parameters': analyzer.get_estimated_parameters(),
        'comparison': comparison,
        'report': report
    }


def log_mode_info(logger: Logger, cfg: Config):
    """Log information about the current input mode"""
    logger.subsection("Input Mode")
    logger.info(cfg.get_mode_description())

    if cfg.mode == 'data_driven' and cfg.data_comparison:
        logger.subsection("Data-Driven Parameter Updates")
        rows = []
        for key, vals in cfg.data_comparison.items():
            rows.append([
                key,
                f"{vals['assumed']:.2f}",
                f"{vals['estimated']:.2f}",
                f"{vals['difference_pct']:+.1f}%"
            ])
        logger.table(
            headers=['Parameter', 'PDF Assumed', 'Data Estimated', 'Diff %'],
            rows=rows
        )


def run_single_scenario(cfg: Config, num_replications: int,
                         matching_name: str, logger: Logger) -> dict:
    """Run a single scenario with multiple replications"""
    logger.section(f"SCENARIO: {cfg.scenario_name} (mode: {cfg.mode})")
    log_mode_info(logger, cfg)

    logger.info(f"Replications: {num_replications}")
    logger.info(f"Matching algorithm: {matching_name}")
    logger.info(f"Simulation time: {cfg.simulation_time} hours")

    matching = get_matching_algorithm(matching_name)
    all_stats = []

    base_seed = cfg.random_seed
    for i in range(num_replications):
        # Update seed for each replication
        # If base_seed is None, use no fixed seed (truly random each run)
        if base_seed is not None:
            cfg.random_seed = base_seed + i
        else:
            cfg.random_seed = None

        sim_config = create_simulation_config(cfg)
        sim = RideSharingSimulation(sim_config, matching)
        stats = sim.run()
        all_stats.append(stats)

        logger.progress(i + 1, num_replications, prefix="Replications")

    analysis = analyze_replications(all_stats)

    logger.subsection(f"Results for {cfg.scenario_name}")
    results_rows = []
    for metric, stat in analysis.items():
        if 'error' not in stat:
            results_rows.append([
                metric,
                f"{stat['mean']:.4f}",
                f"{stat['std']:.4f}",
                f"[{stat['ci_lower']:.4f}, {stat['ci_upper']:.4f}]"
            ])
    logger.table(headers=['Metric', 'Mean', 'Std', '95% CI'], rows=results_rows)

    return {
        'scenario': cfg.scenario_name,
        'mode': cfg.mode,
        'params': cfg.to_dict(),
        'data_comparison': cfg.data_comparison,
        'analysis': analysis,
        'raw_stats': [s.get_summary() for s in all_stats]
    }


def compare_all_scenarios(config_path: str, num_replications: int,
                           matching_name: str, logger: Logger) -> dict:
    """Run and compare all defined scenarios"""
    logger.section("SCENARIO COMPARISON")

    available = get_available_scenarios(config_path)
    results = {}

    for scenario_name in available:
        cfg = Config(config_path=config_path, scenario=scenario_name)
        results[scenario_name] = run_single_scenario(
            cfg, num_replications, matching_name, logger
        )

    logger.section("COMPARISON SUMMARY")

    comparison_rows = []
    for scenario_name, result in results.items():
        analysis = result['analysis']
        mode_tag = f" [{result['mode']}]"
        # Safe extraction with fallback
        def _m(key):
            return analysis.get(key, {}).get('mean', 0)
        fr = _m('fairness_ratio')
        fr_str = f"{fr:.2f}" if fr != float('inf') else "inf"
        comparison_rows.append([
            scenario_name + mode_tag,
            f"{_m('abandonment_rate') * 100:.2f}%",
            f"{_m('avg_waiting_time') * 60:.2f}",
            f"{_m('pickup_waiting_time_p90') * 60:.2f}",
            f"£{_m('avg_net_hourly_earnings'):.2f}",
            f"{fr_str}",
            f"{_m('avg_rest_fraction'):.3f}",
            f"{_m('long_rest_prob_15min'):.3f}",
        ])

    logger.table(
        headers=['Scenario', 'Abandon%', 'Wait(min)', 'P90Wait', 'NetEarn/hr', 'Fair', 'Rest', 'LongRest'],
        rows=comparison_rows
    )

    return results


def save_results(results: dict, output_dir: str, logger: Logger) -> str:
    """Save results to JSON file"""
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(output_dir, f"results_{timestamp}.json")

    def convert(obj):
        if isinstance(obj, float) and (obj == float('inf') or obj == float('-inf') or obj != obj):
            return str(obj)  # "inf", "-inf", "nan"
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        return str(obj)

    with open(filename, 'w') as f:
        json.dump(results, f, indent=2, default=convert)

    logger.info(f"Results saved to: {filename}")
    return filename


def main():
    """Main entry point"""
    args = parse_arguments()

    # Load configuration - scenario determines the mode
    cfg = Config(config_path=args.config, scenario=args.scenario)

    # Override with command line arguments if provided
    if args.time is not None:
        cfg.simulation_time = args.time
    if args.seed is not None:
        cfg.random_seed = args.seed
    if args.output is not None:
        cfg.output_directory = args.output
    if args.verbose:
        cfg.verbose = True

    # Create date-time-stamped output subdirectory under mode folder
    output_dir = get_output_dir_with_datetime(cfg.output_directory, cfg.mode)

    # Set up logger
    logger = setup_logger(
        output_dir=output_dir,
        verbose=args.verbose,
        quiet=args.quiet,
        log_file=cfg.log_file
    )

    try:
        logger.section("BoxCar Ride-Sharing Simulation")
        logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Config file: {args.config}")
        logger.info(f"Output directory: {output_dir}")
        logger.info(f"Log file: {logger.get_log_file_path()}")

        # Analyze data if requested
        data_analysis = None
        if args.analyze_only:
            data_analysis = analyze_data(logger, cfg)
            logger.section("Analysis Complete")
            logger.info("Data analysis finished. No simulation run.")
            return

        # Run simulation
        if args.compare:
            results = compare_all_scenarios(
                args.config, args.replications, args.matching, logger
            )
        else:
            results = run_single_scenario(
                cfg, args.replications, args.matching, logger
            )

        # Save results
        save_results(results, output_dir, logger)

        logger.section("Simulation Complete")
        logger.info(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Log saved to: {logger.get_log_file_path()}")

    except KeyboardInterrupt:
        logger.warning("Simulation interrupted by user")
    except Exception as e:
        logger.error(f"Error during simulation: {e}")
        raise
    finally:
        logger.close()


if __name__ == '__main__':
    main()
