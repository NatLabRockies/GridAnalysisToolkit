# gat/datahelpers/sienna_system.py
"""
Sienna system implementation for GAT.

Provides a concrete implementation of BaseSystem for Sienna/PowerSystems.jl
JSON system files. Extracts generator categories, classifications, and metadata
for palette generation.
"""

import json
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas as pd
from loguru import logger

from gat.datahelpers.base_system import (
    BaseSystem,
    GeneratorCategory,
    LoadCategory,
    SystemInfo,
)


class SiennaSystem(BaseSystem):
    """
    System parser for Sienna/PowerSystems.jl JSON files.

    Reads generator metadata, classifications, and categories from
    Sienna system JSON files. Provides standardized access to system
    data for palette generation and visualization.

    Example usage:
        system = SiennaSystem("path/to/system.json")
        categories = system.list_generator_categories()
        generators = system.get_generator_data()
        info = system.get_system_info()
    """

    # VRE technology patterns
    VRE_TYPES = {
        "Solar",
        "PV",
        "Photovoltaic",
        "Wind",
        "CSP",  # Concentrating Solar Power (if no storage)
    }

    # Storage technology patterns
    STORAGE_TYPES = {
        "Battery",
        "Storage",
        "BESS",
        "Hydro_Pumped",
        "PSH",
    }

    # Generator component types in Sienna
    GENERATOR_TYPES = {
        "RenewableDispatch",
        "RenewableNonDispatch",
        "ThermalStandard",
        "ThermalMultiStart",
        "HydroDispatch",
        "HydroEnergyReservoir",
        "GenericBattery",
        "Storage",
    }

    def __init__(self, system_path: str):
        """
        Initialize Sienna system parser.

        Args:
            system_path: Path to Sienna system JSON file

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file is not valid Sienna JSON
        """
        super().__init__(system_path)
        self._system_data = None
        self._load_system()

    def _load_system(self):
        """Load and parse the Sienna system JSON file."""
        try:
            with open(self.system_path, "r") as f:
                self._system_data = json.load(f)

            # Validate it's a Sienna system file
            if "data" not in self._system_data:
                raise ValueError("Invalid Sienna system file: missing 'data' key")

            if "components" not in self._system_data.get("data", {}):
                raise ValueError(
                    "Invalid Sienna system file: missing 'data.components' key"
                )

            logger.debug(f"Loaded Sienna system from {self.system_path}")

        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON: {e}")
        except Exception as e:
            raise ValueError(f"Failed to load Sienna system file: {e}")

    def get_system_info(self) -> SystemInfo:
        """
        Get basic system information.

        Returns:
            SystemInfo with metadata extracted from Sienna JSON
        """
        components = self._system_data.get("data", {}).get("components", [])

        # Count components by type
        generators = [
            c
            for c in components
            if c.get("__metadata__", {}).get("type") in self.GENERATOR_TYPES
        ]
        buses = [
            c
            for c in components
            if c.get("__metadata__", {}).get("type") in {"Bus", "ACBus"}
        ]
        loads = [
            c
            for c in components
            if c.get("__metadata__", {}).get("type")
            in {"PowerLoad", "StandardLoad", "InterruptiblePowerLoad"}
        ]

        # Extract base power if available
        base_power = self._system_data.get("data", {}).get("base_power")

        return SystemInfo(
            name=self._system_data.get("data", {}).get("name"),
            description=self._system_data.get("data", {}).get("description"),
            base_power=base_power,
            data_format_version=self._system_data.get("data_format_version"),
            num_generators=len(generators),
            num_buses=len(buses),
            num_loads=len(loads),
        )

    def list_component_types(self) -> Set[str]:
        """
        List all component types in the system.

        Returns:
            Set of component type names
        """
        components = self._system_data.get("data", {}).get("components", [])
        return {c.get("__metadata__", {}).get("type") for c in components}

    def _extract_category_name(self, component: Dict) -> str:
        """
        Extract a category name from a generator component.

        Builds a category name from available metadata like fuel type,
        prime mover, or technology classification.

        Args:
            component: Generator component dictionary

        Returns:
            Category name string
        """
        # Try to extract from various fields
        fuel = component.get("fuel")
        prime_mover = component.get("prime_mover")
        tech_type = component.get("technology_type")
        gen_type = component.get("__metadata__", {}).get("type", "")

        # Build category name
        parts = []

        # Handle renewable types — prefer fuel ("Solar", "Wind") for the
        # category name; fall back to prime_mover / technology_type if absent.
        if "Renewable" in gen_type:
            if fuel:
                parts.append(fuel)
            elif prime_mover:
                parts.append(prime_mover)
            elif tech_type:
                parts.append(tech_type)
            else:
                parts.append("Renewable")

        # Handle hydro types
        elif "Hydro" in gen_type:
            parts.append("Hydro")
            if tech_type:
                parts.append(tech_type)

        # Handle thermal types
        elif "Thermal" in gen_type:
            if fuel:
                parts.append(fuel)
            if prime_mover:
                parts.append(prime_mover)
            if not parts:
                parts.append("Thermal")

        # Handle storage/battery
        elif "Battery" in gen_type or "Storage" in gen_type:
            parts.append("Battery")
            if tech_type:
                parts.append(tech_type)

        # Fallback to generator type
        else:
            parts.append(gen_type)

        # Clean up category name
        category = "_".join(parts) if parts else "Unknown"
        return category

    def _is_vre(self, category: str, component: Dict) -> bool:
        """
        Determine if a generator category/component is VRE.

        Args:
            category: Category name
            component: Generator component dict

        Returns:
            True if VRE, False otherwise
        """
        # Check category name
        for vre_type in self.VRE_TYPES:
            if vre_type.lower() in category.lower():
                return True

        # Check generator type
        gen_type = component.get("__metadata__", {}).get("type", "")
        if "RenewableNonDispatch" in gen_type:
            return True

        # Check prime mover
        prime_mover = component.get("prime_mover", "")
        if prime_mover in {"PV", "WT", "Wind", "Solar"}:
            return True

        return False

    def _is_storage(self, category: str, component: Dict) -> bool:
        """
        Determine if a generator category/component is storage.

        Args:
            category: Category name
            component: Generator component dict

        Returns:
            True if storage, False otherwise
        """
        # Check category name
        for storage_type in self.STORAGE_TYPES:
            if storage_type.lower() in category.lower():
                return True

        # Check generator type
        gen_type = component.get("__metadata__", {}).get("type", "")
        if "Battery" in gen_type or "Storage" in gen_type:
            return True

        return False

    def list_generator_categories(self) -> List[GeneratorCategory]:
        """
        List all generator categories in the Sienna system.

        Analyzes generator components and groups them by category
        (fuel type, prime mover, technology). Calculates total capacity
        and classifies as VRE/storage/curtailable.

        Returns:
            List of GeneratorCategory instances with metadata
        """
        components = self._system_data.get("data", {}).get("components", [])
        generators = [
            c
            for c in components
            if c.get("__metadata__", {}).get("type") in self.GENERATOR_TYPES
        ]

        # Group generators by category
        category_data = defaultdict(
            lambda: {
                "components": [],
                "total_capacity": 0.0,
                "is_vre": False,
                "is_storage": False,
            }
        )

        for gen in generators:
            category = self._extract_category_name(gen)

            # Get capacity
            capacity = 0.0
            if "active_power_limits" in gen:
                limits = gen["active_power_limits"]
                if isinstance(limits, dict):
                    capacity = limits.get("max", 0.0)
            elif "rating" in gen:
                capacity = gen.get("rating", 0.0)

            category_data[category]["components"].append(gen)
            category_data[category]["total_capacity"] += capacity

            # Determine classifications (any VRE/storage in category marks it)
            if self._is_vre(category, gen):
                category_data[category]["is_vre"] = True
            if self._is_storage(category, gen):
                category_data[category]["is_storage"] = True

        # Build GeneratorCategory objects
        categories = []
        for cat_name, data in category_data.items():
            # Get representative component for metadata
            rep_gen = data["components"][0]

            category = GeneratorCategory(
                name=cat_name,
                display_name=cat_name.replace("_", " "),
                fuel_type=rep_gen.get("fuel"),
                prime_mover=rep_gen.get("prime_mover"),
                technology=rep_gen.get("technology_type"),
                count=len(data["components"]),
                total_capacity=data["total_capacity"],
                is_vre=data["is_vre"],
                is_storage=data["is_storage"],
                is_curtailable=data["is_vre"],  # VRE is typically curtailable
            )
            categories.append(category)

        # Sort by total capacity (descending)
        categories.sort(key=lambda x: x.total_capacity or 0, reverse=True)

        return categories

    def list_load_categories(self) -> List[LoadCategory]:
        """
        List all load categories in the Sienna system.

        Returns:
            List of LoadCategory instances

        Note:
            Sienna doesn't typically have explicit load categories,
            so this returns a simple list of load types if present.
        """
        components = self._system_data.get("data", {}).get("components", [])
        load_types = {
            "PowerLoad",
            "StandardLoad",
            "InterruptiblePowerLoad",
            "FixedAdmittance",
        }

        loads = [
            c for c in components if c.get("__metadata__", {}).get("type") in load_types
        ]

        # Group by type
        load_categories = {}
        for load in loads:
            load_type = load.get("__metadata__", {}).get("type", "Unknown")

            if load_type not in load_categories:
                load_categories[load_type] = LoadCategory(
                    name=load_type,
                    display_name=load_type.replace("PowerLoad", "Load"),
                    is_flexible="Interruptible" in load_type,
                    count=0,
                    total_demand=0.0,
                )

            load_categories[load_type].count += 1

            # Try to get load magnitude
            if "max_active_power" in load:
                load_categories[load_type].total_demand += load["max_active_power"]
            elif "active_power" in load:
                load_categories[load_type].total_demand += load["active_power"]

        return list(load_categories.values())

    def get_generator_data(self, category: Optional[str] = None) -> pd.DataFrame:
        """
        Get detailed generator data as a DataFrame.

        Args:
            category: Optional category filter

        Returns:
            DataFrame with generator metadata
        """
        components = self._system_data.get("data", {}).get("components", [])
        generators = [
            c
            for c in components
            if c.get("__metadata__", {}).get("type") in self.GENERATOR_TYPES
        ]

        # Extract data
        gen_data = []
        for gen in generators:
            gen_category = self._extract_category_name(gen)

            # Skip if filtering by category
            if category and gen_category != category:
                continue

            # Get capacity
            capacity = 0.0
            if "active_power_limits" in gen:
                limits = gen["active_power_limits"]
                if isinstance(limits, dict):
                    capacity = limits.get("max", 0.0)
            elif "rating" in gen:
                capacity = gen.get("rating", 0.0)

            # Get bus connection
            bus = None
            if "bus" in gen:
                bus_data = gen["bus"]
                if isinstance(bus_data, dict):
                    bus = bus_data.get("value")

            gen_data.append(
                {
                    "name": gen.get("name", "Unknown"),
                    "category": gen_category,
                    "type": gen.get("__metadata__", {}).get("type"),
                    "capacity": capacity,
                    "fuel_type": gen.get("fuel"),
                    "prime_mover": gen.get("prime_mover"),
                    "technology": gen.get("technology_type"),
                    "bus": bus,
                    "available": gen.get("available", True),
                    "is_vre": self._is_vre(gen_category, gen),
                    "is_storage": self._is_storage(gen_category, gen),
                }
            )

        df = pd.DataFrame(gen_data)

        if df.empty:
            # Return empty DataFrame with expected columns
            return pd.DataFrame(
                columns=[
                    "name",
                    "category",
                    "type",
                    "capacity",
                    "fuel_type",
                    "prime_mover",
                    "technology",
                    "bus",
                    "available",
                    "is_vre",
                    "is_storage",
                ]
            )

        return df

    def get_load_data(self, category: Optional[str] = None) -> pd.DataFrame:
        """
        Get detailed load data as a DataFrame.

        Args:
            category: Optional category filter

        Returns:
            DataFrame with load metadata
        """
        components = self._system_data.get("data", {}).get("components", [])
        load_types = {
            "PowerLoad",
            "StandardLoad",
            "InterruptiblePowerLoad",
            "FixedAdmittance",
        }

        loads = [
            c for c in components if c.get("__metadata__", {}).get("type") in load_types
        ]

        # Extract data
        load_data = []
        for load in loads:
            load_type = load.get("__metadata__", {}).get("type", "Unknown")

            # Skip if filtering by category
            if category and load_type != category:
                continue

            # Get demand
            demand = 0.0
            if "max_active_power" in load:
                demand = load["max_active_power"]
            elif "active_power" in load:
                demand = load["active_power"]

            # Get bus connection
            bus = None
            if "bus" in load:
                bus_data = load["bus"]
                if isinstance(bus_data, dict):
                    bus = bus_data.get("value")

            load_data.append(
                {
                    "name": load.get("name", "Unknown"),
                    "category": load_type,
                    "demand": demand,
                    "bus": bus,
                    "is_flexible": "Interruptible" in load_type,
                }
            )

        df = pd.DataFrame(load_data)

        if df.empty:
            # Return empty DataFrame with expected columns
            return pd.DataFrame(
                columns=["name", "category", "demand", "bus", "is_flexible"]
            )

        return df

    def validate(self) -> List[str]:
        """
        Validate the Sienna system file.

        Returns:
            List of warning messages
        """
        warnings_list = super().validate()

        # Check for required Sienna fields
        if "data_format_version" not in self._system_data:
            warnings_list.append("Missing data_format_version")

        data = self._system_data.get("data", {})
        if "base_power" not in data:
            warnings_list.append("Missing base_power")

        # Check for generator issues
        generators = self.get_generator_data()
        if not generators.empty:
            # Check for generators with no capacity
            no_capacity = generators[generators["capacity"] == 0]
            if len(no_capacity) > 0:
                warnings_list.append(
                    f"{len(no_capacity)} generators have zero capacity"
                )

            # Check for missing fuel/prime mover on thermal units
            thermal = generators[
                generators["category"].str.contains("Thermal", na=False)
            ]
            if not thermal.empty:
                no_fuel = thermal[thermal["fuel_type"].isna()]
                if len(no_fuel) > 0:
                    warnings_list.append(
                        f"{len(no_fuel)} thermal generators missing fuel type"
                    )

        return warnings_list
