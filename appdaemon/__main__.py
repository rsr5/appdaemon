#!/usr/bin/python3

"""AppDaemon main() module.

AppDaemon module that contains main() along with argument parsing, instantiation of the AppDaemon and HTTP Objects,
also creates the loop and kicks everything off

"""

import argparse
import asyncio
import functools
import itertools
import json
import logging
import logging.config
import os
import signal
import sys
from collections.abc import Callable
from contextlib import ExitStack, contextmanager
from logging import Logger
from pathlib import Path

from pydantic import ValidationError

import appdaemon.appdaemon as ad
import appdaemon.utils as utils
from appdaemon import exceptions as ade
from appdaemon.app_management import UpdateMode
from appdaemon.appdaemon import AppDaemon
from appdaemon.exceptions import NoADConfig, StartupAbortedException
from appdaemon.http import HTTP
from appdaemon.logging import Logging

from .models.config.yaml import MainConfig

logger = logging.getLogger(__name__)
err_logger = logging.getLogger("bare")

try:
    import pid
except ImportError:
    pid = None

try:
    import uvloop
except ImportError:
    uvloop = None


# This dict sets up the default logging before the config has even been read.
PRE_LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'bare': {
            'format': "{levelname}: {message}",
            'style': '{',
        },
        'full': {
            'format': "{asctime}.{msecs:03.0f} {levelname} AppDaemon: {message}",
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        }
    },
    'handlers': {
        'stdout': {
            'class': 'logging.StreamHandler',
            'formatter': 'full',
            'stream': 'ext://sys.stdout'
        },
        'stderr': {
            'class': 'logging.StreamHandler',
            'formatter': 'bare',
            'stream': 'ext://sys.stderr'
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['stdout'],
    },
    'loggers': {
        'bare': {
            'handlers': ['stderr'],
            'propagate': False
        }
    }
}


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed command line arguments.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-c",
        "--config",
        help="full path to config directory",
        type=str,
    )
    parser.add_argument("-p", "--pidfile", help="full path to PID File", default=None)
    parser.add_argument(
        "-t",
        "--timewarp",
        help="speed that the scheduler will work at for time travel",
        type=float,
    )
    parser.add_argument(
        "-s",
        "--starttime",
        help="start time for scheduler <YYYY-MM-DD HH:MM:SS|YYYY-MM-DD#HH:MM:SS>",
        type=str,
    )
    parser.add_argument(
        "-e",
        "--endtime",
        help="end time for scheduler <YYYY-MM-DD HH:MM:SS|YYYY-MM-DD#HH:MM:SS>",
        type=str,
    )
    parser.add_argument(
        "-C",
        "--configfile",
        help="name for config file",
        type=str,
    )
    parser.add_argument(
        "-D",
        "--debug",
        help="global debug level",
        # default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    parser.add_argument("-m", "--moduledebug", nargs=2, action="append")
    parser.add_argument("-v", "--version", action="version", version="%(prog)s " + utils.__version__)
    parser.add_argument("--profiledash", help=argparse.SUPPRESS, action="store_true")
    parser.add_argument("--write_toml", help="use TOML for creating new app configuration files", action="store_true")
    # TODO Implement --write_toml
    parser.add_argument("--toml", help="Deprecated", action="store_true")

    return parser.parse_args()


def resolve_config_file(args: argparse.Namespace) -> tuple[Path, Path]:
    """Resolve configuration file and directory paths.

    Args:
        args: Parsed command line arguments

    Returns:
        Tuple of (config_file, config_dir) paths

    Raises:
        NoADConfig: If no valid configuration file is found
    """
    default_config_files = [
        "appdaemon.toml",
        "appdaemon.yaml",
    ]
    default_config_paths = [Path("~/.homeassistant").expanduser(), Path("/etc/appdaemon"), Path("/conf")]

    if args.configfile is not None:
        config_file = Path(args.configfile).resolve()
        if args.config is not None:
            config_dir = Path(args.config).resolve()
        else:
            config_dir = config_file.parent
    else:
        if args.config is not None:
            config_dir = Path(args.config).resolve()
            for file in default_config_files:
                if (config_file := (config_dir / file)).exists():
                    break
            else:
                raise NoADConfig(f"{config_file} not found")
        else:
            all_default_config_paths = itertools.product(default_config_files, default_config_paths)
            for file in all_default_config_paths:
                dir = file[1]
                final_path = dir / file[0]
                if (config_file := final_path).exists():
                    break
            else:
                raise NoADConfig(f"No valid configuration file found in default locations: {[str(d) for d in default_config_paths]}")

    if not config_file.exists():
        raise NoADConfig(f"{config_file} does not exist")
    if not os.access(config_file, os.R_OK):
        raise NoADConfig(f"{config_file} is not readable")

    return config_file, config_dir


def parse_config(stop_function: Callable) -> tuple[MainConfig, argparse.Namespace]:
    """Parse configuration file and return MainConfig model.

    Args:
        stop_function: Function to call for stopping the application

    Returns:
        Tuple of MainConfig model instance and parsed arguments

    Raises:
        SystemExit: If configuration cannot be loaded or parsed
    """
    # Get command line args
    args = parse_arguments()

    if args.debug is not None:
        CLI_LOG_CFG = PRE_LOGGING.copy()
        CLI_LOG_CFG["root"]["level"] = args.debug
        logging.config.dictConfig(CLI_LOG_CFG)
        logger.debug("Configured logging level from command line argument")

    try:
        config_file, config_dir = resolve_config_file(args)
    except NoADConfig as e:
        err_logger.error(f"Error accessing configuration: {e}")
        sys.exit(1)

    try:
        config = utils.read_config_file(config_file)
        assert isinstance(config, dict), "Configuration file must be a dictionary"

        # Only process sections that actually have None values
        for key, value in config.items():
            if value is None:
                config[key] = {}

        ad_kwargs = config["appdaemon"]
        assert isinstance(ad_kwargs, dict), "AppDaemon configuration must be a dictionary"

        # Batch assign required parameters
        ad_kwargs.update({
            "config_dir": config_dir,
            "config_file": config_file,
            "write_toml": args.write_toml,
            "stop_function": stop_function,
        })

        # Conditionally assign time-related parameters
        for attr in ("timewarp", "starttime", "endtime"):
            if (value := getattr(args, attr)):
                ad_kwargs[attr] = value

        # Set log level with fallback
        ad_kwargs["loglevel"] = args.debug or ad_kwargs.get("loglevel", "INFO")

        # Handle module debug efficiently
        module_debug_cli = (
            {arg[0]: arg[1] for arg in args.moduledebug}
            if args.moduledebug else {}
        )

        if isinstance(ad_kwargs.get("module_debug"), dict):
            ad_kwargs["module_debug"] |= module_debug_cli
        else:
            ad_kwargs["module_debug"] = module_debug_cli

        if isinstance((hadashboard := config.get("hadashboard")), dict):
            hadashboard["config_dir"] = config_dir
            hadashboard["config_file"] = config_file
            hadashboard["dashboard"] = True
            hadashboard["profile_dashboard"] = args.profiledash

        model = MainConfig.model_validate(config)

        if ad_kwargs["loglevel"] == "DEBUG":
            # need to dump as python types or serializing the timezone object will fail
            model_json = model.model_dump(mode="python", by_alias=True)
            logger.debug(json.dumps(model_json, indent=4, default=str, sort_keys=True))

        return model, args
    except ValidationError as e:
        err_logger.error(f"Configuration error in: {config_file}")
        err_logger.error(e)
        sys.exit(1)
    except ade.ConfigReadFailure as e:
        ade.user_exception_block(err_logger, e, config_dir, "Reading AppDaemon configuration")
        sys.exit(1)
    except Exception as e:
        err_logger.error(f"Unexpected error loading config file: {config_file}")
        err_logger.error(e)
        sys.exit(1)


class ADMain:
    """
    Class to encapsulate all main() functionality.
    """

    AD: AppDaemon
    loop: asyncio.AbstractEventLoop

    logging: Logging
    logger: Logger
    error: Logger
    diag: Logger
    AD: AppDaemon
    _cleanup_stack: ExitStack

    model: MainConfig
    args: argparse.Namespace

    def __init__(self):
        """Constructor."""
        self.http_object = None
        self._cleanup_stack = ExitStack()

    def __enter__(self):
        self.model, self.args = parse_config(self.stop)
        self._cleanup_stack.__enter__()

        self.setup_logging()

        if self.args.pidfile is not None and pid is not None:
            self.logger.info("Using pidfile: %s", self.args.pidfile)
            pidfile_path = Path(self.args.pidfile)
            pid_file = pid.PidFile(pidfile_path.name, pidfile_path.parent)
            try:
                self.enter_context(pid_file)
            except pid.PidFileError:
                self.logger.error("Unable to acquire pidfile - terminating")
                sys.exit(1)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # Then handle any additional cleanup via the stack
        self._cleanup_stack.close()
        del self.model
        del self.args

    def add_cleanup(self, cleanup_func, *args, **kwargs):
        """Add a cleanup function to be called on exit."""
        self._cleanup_stack.callback(cleanup_func, *args, **kwargs)

    def enter_context(self, context_manager):
        """Enter a context manager and ensure it's cleaned up on exit."""
        return self._cleanup_stack.enter_context(context_manager)

    def handle_sig(self, signum: int):
        """Function to handle signals.

        Signals:
            SIGUSR1 will result in internal info being dumped to the DIAG log
            SIGHUP will force a reload of all apps
            SIGINT and SIGTEM both result in AD shutting down
        """
        match signum:
            case signal.SIGUSR1:
                self.AD.thread_async.call_async_no_wait(self.AD.sched.dump_schedule)
                self.AD.thread_async.call_async_no_wait(self.AD.callbacks.dump_callbacks)
                self.AD.thread_async.call_async_no_wait(self.AD.threading.dump_threads)
                self.AD.thread_async.call_async_no_wait(self.AD.app_management.dump_objects)
                self.AD.thread_async.call_async_no_wait(self.AD.sched.dump_sun)
            case signal.SIGHUP:
                self.AD.thread_async.call_async_no_wait(self.AD.app_management.check_app_updates, mode=UpdateMode.TERMINATE)
            case signal.SIGINT:
                self.logger.info("Keyboard interrupt")
                self.stop()
            case signal.SIGTERM:
                self.logger.info("SIGTERM Received")
                self.stop()
            # case signal.SIGWINCH:
            #     ... # disregard window changes
            # case _:
            #     self.logger.error(f'Unhandled signal: {signal.Signals(signum).name}')

    @contextmanager
    def signal_handlers(self, loop: asyncio.AbstractEventLoop):
        """Context manager for signal handler registration and cleanup."""
        registered_signals = []
        try:
            for sig in signal.Signals:
                callback = functools.partial(self.handle_sig, sig)
                try:
                    loop.add_signal_handler(sig.value, callback)
                    registered_signals.append(sig.value)
                except RuntimeError:
                    # This happens for some signals on some operating systems, no problem
                    continue
            yield
        finally:
            for sig_value in registered_signals:
                try:
                    loop.remove_signal_handler(sig_value)
                except (ValueError, RuntimeError):
                    # Signal handler might not be registered or already removed
                    pass

    def stop(self):
        """Called by the signal handler to shut AD down."""
        self.AD.stop()
        if self.http_object is not None:
            self.http_object.stop()

    def run(self):
        """Start AppDaemon up after initial argument parsing."""
        assert getattr(self, 'model', None) is not None, "Model must be initialized before running"

        # uvloop needs to be installed outside of self.run_context
        if self.model.appdaemon.uvloop and uvloop is not None:
            self.logger.info("Running AD using uvloop")
            uvloop.install()

        # async event loop is created here so that it can be referenced later
        self.loop = asyncio.new_event_loop()

        # self.run_context contains the logic for handling exceptions and cleanup
        with self.run_context(self.loop):
            self.logger.debug("Start Main Loop")
            self.AD.start()

            pending = asyncio.all_tasks(self.loop)
            self.loop.run_until_complete(asyncio.gather(*pending))

    @contextmanager
    def run_context(self, loop: asyncio.AbstractEventLoop):
        """Context manager for the main run logic with exception handling."""
        try:
            # Initialize AppDaemon
            self.AD = ad.AppDaemon(self.logging, loop, self._cleanup_stack, self.model.appdaemon)
            loop.set_exception_handler(functools.partial(ade.exception_handler, self.AD))

            # Register signal handlers with cleanup stack
            self.enter_context(self.signal_handlers(loop))

            # Initialize Dashboard/API/admin
            http_components = (
                self.model.hadashboard,
                self.model.old_admin,
                self.model.admin,
                self.model.api,
            )
            http_auto_enable = any(arg is not None for arg in http_components)

            if self.model.http is not None and http_auto_enable:
                self.logger.info("Initializing HTTP")
                self.http_object = HTTP(self.AD, self.model)
                self.AD.register_http(self.http_object)
            else:
                if self.model.http is not None:
                    self.logger.warning("HTTP component is enabled but no consumers are configured - disabling")
                else:
                    self.logger.info("HTTP is disabled")

            yield
            self.logger.debug('Exited self.run_context')

            # Now we are shutting down - perform any necessary cleanup
            self.AD.terminate()
            self.logger.info("AppDaemon is stopped.")
        except ValidationError as e:
            logging.getLogger().exception(e)
        except StartupAbortedException as e:
            # We got an unrecoverable error during startup so print it out and quit
            self.logger.error(f"AppDaemon terminated with errors: {e}")
        except ade.AppDaemonException as e:
            ade.user_exception_block(self.logger, e, self.AD.app_dir)
        except Exception:
            self.logger.warning("-" * 60)
            self.logger.warning("Unexpected error during run()")
            self.logger.warning("-" * 60, exc_info=True)
            self.logger.warning("-" * 60)

            self.logger.debug("End Loop")
            self.logger.info("AppDaemon Exited")

    def setup_logging(self) -> None:
        """Set up logging configuration and timezone.
        """
        log_cfg = self.model.logs.model_dump(mode="python", by_alias=True, exclude_unset=True)
        self.logging = Logging(log_cfg, self.args.debug)
        self.logger = self.logging.get_logger()

        if self.model.appdaemon.time_zone is not None:
            self.logging.set_tz(self.model.appdaemon.time_zone)

    def main(self):
        # Startup message
        self.logger.info("-" * 60)
        self.logger.info("AppDaemon Version %s starting", utils.__version__)

        if utils.__version_comments__ is not None and utils.__version_comments__ != "":
            self.logger.info("Additional version info: %s", utils.__version_comments__)

        self.logger.info("-" * 60)
        self.logger.info(
            "Python version is %s.%s.%s",
            sys.version_info[0],
            sys.version_info[1],
            sys.version_info[2],
        )
        self.logger.info("Configuration read from: %s", self.model.appdaemon.config_file)

        utils.deprecation_warnings(self.model.appdaemon, self.logger)

        self.logging.dump_log_config()
        self.logger.debug("AppDaemon Section: %s", self.model.appdaemon)
        self.logger.debug("HADashboard Section: %s", self.model.hadashboard)

        self.run()


def main():
    with ADMain() as admain:
        admain.main()


if __name__ == "__main__":
    """Called when run from the command line."""
    main()
