"""
Monitoring and health check utilities.

This module provides:
- Health check functionality
- Metrics collection
- Service status monitoring
"""

import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import requests

from config import config

logger = logging.getLogger(__name__)


class HealthChecker:
    """Health check manager for application monitoring."""

    def __init__(self):
        """Initialize health checker."""
        self.start_time = time.time()
        self.last_check = None

    def get_uptime(self) -> float:
        """
        Get application uptime in seconds.

        Returns:
            Uptime in seconds
        """
        return time.time() - self.start_time

    def get_uptime_formatted(self) -> str:
        """
        Get formatted uptime string.

        Returns:
            Human-readable uptime (e.g., "2h 34m 12s")
        """
        uptime = self.get_uptime()
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        seconds = int(uptime % 60)

        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")

        return " ".join(parts)

    def check_ollama_health(self) -> bool:
        """
        Check if Ollama service is available.

        Returns:
            True if Ollama is healthy, False otherwise
        """
        try:
            # Try to connect to Ollama API
            response = requests.get(
                f"{config.ollama_base_url}/api/tags",
                timeout=5
            )
            is_healthy = response.status_code == 200

            if is_healthy:
                logger.debug("Ollama health check: OK")
            else:
                logger.warning(
                    f"Ollama health check: FAILED (status {response.status_code})"
                )

            return is_healthy

        except requests.RequestException as e:
            logger.warning(f"Ollama health check: FAILED ({e})")
            return False

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get comprehensive health status.

        Returns:
            Dictionary with health status information
        """
        self.last_check = datetime.now()

        # Check Ollama
        ollama_healthy = self.check_ollama_health()

        # Overall status
        status = "healthy" if ollama_healthy else "degraded"

        return {
            "status": status,
            "timestamp": self.last_check.isoformat(),
            "uptime_seconds": self.get_uptime(),
            "uptime": self.get_uptime_formatted(),
            "components": {
                "ollama": {
                    "status": "healthy" if ollama_healthy else "unhealthy",
                    "url": config.ollama_base_url,
                },
                "app": {
                    "status": "healthy",
                    "version": "1.0.0",
                },
            },
            "config": {
                "environment": config.environment,
                "debug": config.debug,
                "llm_model": config.llm_model,
            }
        }


class MetricsCollector:
    """Collect application metrics."""

    def __init__(self):
        """Initialize metrics collector."""
        self.metrics = {
            "generation_requests": 0,
            "generation_success": 0,
            "generation_failures": 0,
            "validation_failures": 0,
            "total_generation_time": 0.0,
            "requests_by_hour": {},
        }

    def record_generation_request(self):
        """Record a generation request."""
        self.metrics["generation_requests"] += 1

        # Track by hour
        current_hour = datetime.now().strftime("%Y-%m-%d %H:00")
        if current_hour not in self.metrics["requests_by_hour"]:
            self.metrics["requests_by_hour"][current_hour] = 0
        self.metrics["requests_by_hour"][current_hour] += 1

        logger.debug(f"Metrics: generation request #{self.metrics['generation_requests']}")

    def record_generation_success(self, duration: float):
        """
        Record a successful generation.

        Args:
            duration: Generation duration in seconds
        """
        self.metrics["generation_success"] += 1
        self.metrics["total_generation_time"] += duration

        logger.info(
            f"Metrics: generation success (duration: {duration:.2f}s, "
            f"total: {self.metrics['generation_success']})"
        )

    def record_generation_failure(self):
        """Record a failed generation."""
        self.metrics["generation_failures"] += 1

        logger.warning(
            f"Metrics: generation failure "
            f"(total: {self.metrics['generation_failures']})"
        )

    def record_validation_failure(self):
        """Record a validation failure."""
        self.metrics["validation_failures"] += 1

        logger.warning(
            f"Metrics: validation failure "
            f"(total: {self.metrics['validation_failures']})"
        )

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get all collected metrics.

        Returns:
            Dictionary with metrics
        """
        # Calculate success rate
        total_generations = (
            self.metrics["generation_success"] +
            self.metrics["generation_failures"]
        )
        if total_generations > 0:
            success_rate = (
                self.metrics["generation_success"] / total_generations * 100
            )
        else:
            success_rate = 0.0

        # Calculate average generation time
        if self.metrics["generation_success"] > 0:
            avg_generation_time = (
                self.metrics["total_generation_time"] /
                self.metrics["generation_success"]
            )
        else:
            avg_generation_time = 0.0

        return {
            **self.metrics,
            "success_rate": round(success_rate, 2),
            "average_generation_time": round(avg_generation_time, 2),
        }

    def cleanup_old_hourly_data(self, keep_hours: int = 24):
        """
        Remove old hourly request data.

        Args:
            keep_hours: Number of hours to keep (default 24)
        """
        cutoff_time = datetime.now() - timedelta(hours=keep_hours)
        cutoff_str = cutoff_time.strftime("%Y-%m-%d %H:00")

        # Remove old entries
        old_keys = [
            key for key in self.metrics["requests_by_hour"]
            if key < cutoff_str
        ]

        for key in old_keys:
            del self.metrics["requests_by_hour"][key]

        if old_keys:
            logger.debug(f"Cleaned up {len(old_keys)} old hourly metric entries")


# Global instances
health_checker = HealthChecker()
metrics_collector = MetricsCollector()
