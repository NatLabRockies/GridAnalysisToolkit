"""Sienna system implementation for GAT v1.0.0.

Wraps the existing SiennaSystemParser to implement the BaseSystem interface,
exposing Sienna JSON system files as generic named datasets.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger

from ..categories import CategoryMap
from ..datasets import DatasetComposition, DatasetInfo, DatasetKind
from ..interfaces import BaseSystem


# Component types that represent generators (for the "generators" composition)
_GENERATOR_TYPES = {
    "ThermalStandard",
    "ThermalMultiStart",
    "RenewableDispatch",
    "RenewableNonDispatch",
    "HydroDispatch",
    "HydroEnergyReservoir",
    "EnergyReservoirStorage",
    "GenericBattery",
}

# Component types that represent loads
_LOAD_TYPES = {
    "StandardLoad",
    "PowerLoad",
    "FixedAdmittance",
    "InterruptibleLoad",
}

# Component types that represent branches/lines
_BRANCH_TYPES = {
    "Line",
    "MonitoredLine",
    "TapTransformer",
    "Transformer2W",
    "TwoTerminalHVDCLine",
    "PhaseShiftingTransformer",
}


class SiennaSystem(BaseSystem):
    """Sienna system implementation wrapping SiennaSystemParser.

    Exposes component types as named datasets and provides default
    category maps derived from system topology (area, fuel, etc.).

    Args:
        system_path: Path to the Sienna JSON system file.
        generator_types: Override the set of component types considered generators.
        load_types: Override the set of component types considered loads.
        branch_types: Override the set of component types considered branches.
    """

    def __init__(
        self,
        system_path: str | Path,
        generator_types: set[str] | None = None,
        load_types: set[str] | None = None,
        branch_types: set[str] | None = None,
    ) -> None:
        from ..datahelpers.sienna import SiennaSystemParser

        self._parser = SiennaSystemParser(str(system_path))
        self._component_types: set[str] = self._parser.list_components()

        self._generator_types = generator_types or (_GENERATOR_TYPES & self._component_types)
        self._load_types = load_types or (_LOAD_TYPES & self._component_types)
        self._branch_types = branch_types or (_BRANCH_TYPES & self._component_types)

        # Cache for flattened DataFrames
        self._cache: dict[str, pd.DataFrame] = {}

        logger.info(
            "SiennaSystem loaded: {} component types, {} generator types, {} load types",
            len(self._component_types),
            len(self._generator_types),
            len(self._load_types),
        )

    @property
    def parser(self) -> object:
        """Access the underlying SiennaSystemParser for advanced use."""
        return self._parser

    def list_datasets(self) -> list[DatasetInfo]:
        result: list[DatasetInfo] = []

        # Raw component datasets
        for ct in sorted(self._component_types):
            result.append(DatasetInfo(
                name=ct,
                description=f"Sienna {ct} components",
                kind=DatasetKind.RAW_SYSTEM,
                entity_column="name",
            ))

        # Composed datasets
        if self._generator_types:
            result.append(DatasetInfo(
                name="generators",
                description="All generator components",
                kind=DatasetKind.COMPOSED,
                entity_column="name",
                source_datasets=sorted(self._generator_types),
            ))

        if self._load_types:
            result.append(DatasetInfo(
                name="loads",
                description="All load components",
                kind=DatasetKind.COMPOSED,
                entity_column="name",
                source_datasets=sorted(self._load_types),
            ))

        if self._branch_types:
            result.append(DatasetInfo(
                name="branches",
                description="All branch/line components",
                kind=DatasetKind.COMPOSED,
                entity_column="name",
                source_datasets=sorted(self._branch_types),
            ))

        return result

    def get_dataset(self, name: str) -> pd.DataFrame:
        if name in self._cache:
            return self._cache[name]

        # Check composed datasets
        composed_names = {"generators": self._generator_types,
                          "loads": self._load_types,
                          "branches": self._branch_types}

        if name in composed_names:
            source_types = composed_names[name]
            if not source_types:
                raise KeyError(f"No component types found for composed dataset '{name}'")
            frames = []
            for ct in sorted(source_types):
                try:
                    df = self._get_component_flat(ct)
                    frames.append(df)
                except Exception as e:
                    logger.warning("Failed to get component '{}': {}", ct, e)
            if not frames:
                raise KeyError(f"No data available for composed dataset '{name}'")
            result = pd.concat(frames, ignore_index=True)
            self._cache[name] = result
            return result

        # Raw component dataset
        if name in self._component_types:
            df = self._get_component_flat(name)
            self._cache[name] = df
            return df

        available = sorted(self._component_types) + [
            k for k, v in composed_names.items() if v
        ]
        raise KeyError(f"Dataset '{name}' not found. Available: {available}")

    def get_default_category_maps(self) -> list[CategoryMap]:
        maps: list[CategoryMap] = []

        # native_area: generator name → area (via bus→area relationship)
        try:
            area_mapping = self._build_area_mapping()
            if area_mapping:
                maps.append(CategoryMap(
                    name="native_area",
                    description="Native model area from bus topology",
                    mapping=area_mapping,
                ))
        except Exception as e:
            logger.warning("Could not build native_area category map: {}", e)

        # fuel: generator name → fuel type (from component data)
        try:
            fuel_mapping = self._build_fuel_mapping()
            if fuel_mapping:
                maps.append(CategoryMap(
                    name="fuel",
                    description="Fuel type from system data",
                    mapping=fuel_mapping,
                    applies_to=["generation"],
                ))
        except Exception as e:
            logger.warning("Could not build fuel category map: {}", e)

        # prime_mover: generator name → prime mover type
        try:
            pm_mapping = self._build_prime_mover_mapping()
            if pm_mapping:
                maps.append(CategoryMap(
                    name="prime_mover",
                    description="Prime mover type from system data",
                    mapping=pm_mapping,
                    applies_to=["generation"],
                ))
        except Exception as e:
            logger.warning("Could not build prime_mover category map: {}", e)

        return maps

    def get_generator_ratings(self) -> dict[str, float]:
        """Build a unified {entity_name: rating_MW} map across all generator types.

        Uses Sienna's canonical active-power-max convention. For each component:

        - ThermalStandard / ThermalMultiStart / HydroDispatch / HydroEnergyReservoir:
          ``active_power_limits.max * base_power`` (per-unit on device base × MVA base)
        - RenewableDispatch / RenewableNonDispatch: ``rating * base_power``
          (Sienna's `rating` field IS the active-power max for renewables, in
          per-unit on device base)
        - EnergyReservoirStorage / GenericBattery: tries
          ``output_active_power_limits.max * base_power``, then falls back to
          ``rating * base_power``

        The common pattern is always ``<active power max in per-unit> × base_power``.
        Falls back across fields (active_power_limits → rating) so the method
        works for all generator types in a single iteration.

        Returns:
            {entity_name: capacity_mw} mapping. Missing/invalid entries are skipped.
        """
        mapping: dict[str, float] = {}
        gen_types = self._generator_types

        for comp_type in gen_types:
            try:
                raw = self._parser.get_component(comp_type, expand_ext=True)
                if raw is None:
                    continue
                raw = raw.reset_index()

                for _, row in raw.iterrows():
                    name = row.get("name")
                    if not name:
                        continue

                    bp = row.get("base_power")
                    try:
                        bp_val = float(bp) if bp is not None else 0.0
                    except (TypeError, ValueError):
                        continue
                    if bp_val <= 0:
                        continue

                    rating_pu = self._extract_active_power_max_pu(row, raw.columns)
                    if rating_pu is not None and rating_pu > 0:
                        mapping[str(name)] = rating_pu * bp_val

            except Exception as e:
                logger.debug("Could not get generator ratings for '{}': {}", comp_type, e)

        return mapping

    @staticmethod
    def _extract_active_power_max_pu(row: pd.Series, columns: pd.Index) -> float | None:
        """Extract a generator's active-power max in per-unit on its base_power.

        Tries (in order):
          1. active_power_limits.max (canonical for thermal/hydro)
          2. output_active_power_limits.max (canonical for storage discharge)
          3. rating (canonical for renewables)
        """
        for limit_col in ("active_power_limits", "output_active_power_limits"):
            if limit_col in columns:
                v = row.get(limit_col)
                if isinstance(v, dict):
                    m = v.get("max")
                    if m is not None:
                        try:
                            return float(m)
                        except (TypeError, ValueError):
                            pass
        if "rating" in columns:
            r = row.get("rating")
            if r is not None:
                try:
                    return float(r)
                except (TypeError, ValueError):
                    pass
        return None

    def get_branch_ratings(self, base_power: float | None = None) -> dict[str, float]:
        """Build a unified {entity_name: rating_MW} map across all branch types.

        Sienna stores Line/MonitoredLine ratings in per-unit. If ``base_power``
        is provided, those values are multiplied to produce MW ratings that are
        comparable with simulation flow data (which is already in MW).

        TwoTerminalHVDCLine and AreaInterchange limits are already in MW and
        are not scaled.

        Handles different rating column formats:
        - Line/MonitoredLine: ``rating`` (v4) or ``rate`` (v3) column — per-unit
        - TwoTerminalHVDCLine: ``active_power_limits_from`` dict — MW
        - AreaInterchange: ``flow_limits`` dict {from_to, to_from} — MW

        Args:
            base_power: System base power in MW for per-unit → MW conversion.
                If None, ratings are returned in their raw (per-unit) form.
        """
        # Component types whose ratings are in per-unit (need scaling)
        _PER_UNIT_TYPES = {"Line", "MonitoredLine", "TapTransformer",
                           "Transformer2W", "PhaseShiftingTransformer"}
        mapping: dict[str, float] = {}

        # All component types that might carry flow data
        flow_types = (
            self._branch_types | {"AreaInterchange"}
        ) & self._component_types

        for comp_type in flow_types:
            try:
                raw = self._parser.get_component(comp_type, expand_ext=True)
                if raw is None:
                    continue
                raw = raw.reset_index()

                scale = base_power if (base_power and comp_type in _PER_UNIT_TYPES) else 1.0

                for _, row in raw.iterrows():
                    name = row.get("name")
                    if not name:
                        continue

                    rating = self._extract_rating(row, raw.columns)
                    if rating is not None:
                        mapping[str(name)] = rating * scale

            except Exception as e:
                logger.debug("Could not get ratings for '{}': {}", comp_type, e)

        return mapping

    @staticmethod
    def _extract_rating(row: pd.Series, columns: pd.Index) -> float | None:
        """Extract a rating value from a component row, trying multiple formats."""
        # Simple numeric rating/rate column
        for col in ("rating", "rate"):
            if col in columns:
                val = row.get(col)
                if val is not None and not isinstance(val, (dict, list)):
                    try:
                        return float(val)
                    except (TypeError, ValueError):
                        pass

        # Nested flow_limits dict (AreaInterchange): {from_to: X, to_from: Y}
        if "flow_limits" in columns:
            fl = row.get("flow_limits")
            if isinstance(fl, dict):
                vals = [v for v in fl.values() if isinstance(v, (int, float))]
                if vals:
                    return float(max(vals))

        # Nested active_power_limits (TwoTerminalHVDCLine)
        for col in ("active_power_limits_from", "active_power_limits_to"):
            if col in columns:
                val = row.get(col)
                if isinstance(val, dict):
                    nums = [v for v in val.values() if isinstance(v, (int, float))]
                    if nums:
                        return float(max(abs(n) for n in nums))
                elif isinstance(val, (int, float)):
                    return float(abs(val))

        return None

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _get_component_flat(self, component_type: str) -> pd.DataFrame:
        """Get a component as a flat DataFrame with 'name' as a regular column."""
        raw = self._parser.get_component(component_type, expand_ext=True)
        if raw is None:
            raise KeyError(f"Component type '{component_type}' not found")

        df = raw.reset_index()

        # Flatten nested dict/list columns to strings and drop internal metadata
        cols_to_drop = []
        for col in df.columns:
            if col in ("__metadata__", "internal", "ext"):
                cols_to_drop.append(col)
            elif df[col].dtype == object:
                # Check if values are dicts/lists and flatten them
                sample = df[col].dropna().head(1)
                if len(sample) > 0 and isinstance(sample.iloc[0], (dict, list)):
                    # For bus references, extract the UUID value
                    if col == "bus":
                        df[col] = df[col].apply(
                            lambda x: x.get("value", str(x)) if isinstance(x, dict) else str(x)
                        )
                    elif col == "area":
                        df[col] = df[col].apply(
                            lambda x: x.get("value", str(x)) if isinstance(x, dict) else str(x)
                        )
                    else:
                        cols_to_drop.append(col)

        df = df.drop(columns=cols_to_drop, errors="ignore")

        # Cast float64 to float32
        float_cols = df.select_dtypes(include=[np.float64]).columns
        if len(float_cols) > 0:
            df[float_cols] = df[float_cols].astype(np.float32)

        return df

    def _build_area_mapping(self) -> dict[str, str]:
        """Build entity_name → area mapping for all bus-connected components."""
        mapping: dict[str, str] = {}

        # Get bus→area relationship (area_column=None resolves UUIDs to names)
        bus_area = self._parser.get_bus_area_relation(area_column=None)
        if not bus_area:
            return mapping

        # Map all component types that have a bus relationship
        # (generators, loads, storage, etc.)
        bus_connected_types = (
            self._generator_types | self._load_types | {"HydroPumpedStorage"}
        ) & self._component_types

        for comp_type in bus_connected_types:
            try:
                comp_bus = self._parser.get_component_bus_relation(comp_type)
                if comp_bus:
                    for name, bus_uuid in comp_bus.items():
                        area = bus_area.get(bus_uuid)
                        if area:
                            mapping[name] = str(area)
            except Exception as e:
                logger.debug("Could not get bus relation for '{}': {}", comp_type, e)

        return mapping

    def _build_fuel_mapping(self) -> dict[str, str]:
        """Build generator_name → fuel mapping from component data."""
        mapping: dict[str, str] = {}

        for gen_type in self._generator_types:
            try:
                raw = self._parser.get_component(gen_type, expand_ext=True)
                if raw is not None and "fuel" in raw.columns:
                    for _, row in raw.iterrows():
                        name = row.get("name")
                        fuel = row.get("fuel")
                        if name and fuel and not isinstance(fuel, (dict, list)):
                            mapping[str(name)] = str(fuel)
            except Exception as e:
                logger.debug("Could not get fuel for '{}': {}", gen_type, e)

        return mapping

    def _build_prime_mover_mapping(self) -> dict[str, str]:
        """Build generator_name → prime_mover mapping from component data."""
        mapping: dict[str, str] = {}

        for gen_type in self._generator_types:
            try:
                raw = self._parser.get_component(gen_type, expand_ext=True)
                if raw is not None and "prime_mover_type" in raw.columns:
                    for _, row in raw.iterrows():
                        name = row.get("name")
                        pm = row.get("prime_mover_type")
                        if name and pm and not isinstance(pm, (dict, list)):
                            mapping[str(name)] = str(pm)
            except Exception as e:
                logger.debug("Could not get prime_mover for '{}': {}", gen_type, e)

        return mapping

    def get_bus_coordinates(self) -> pd.DataFrame:
        """Extract bus coordinates from the Sienna system JSON's GeometricInfo."""
        try:
            bus_geo = self._parser._get_bus_geo()
            # bus_geo is a GeoDataFrame with geometry column + bus properties
            result = pd.DataFrame({
                "name": bus_geo["name"].values,
                "UUID": bus_geo["UUID"].values,
                "latitude": bus_geo.geometry.y.values,
                "longitude": bus_geo.geometry.x.values,
            })
            logger.info("Extracted {} bus coordinates from system JSON", len(result))
            return result
        except Exception as e:
            logger.warning("Could not extract bus coordinates: {}", e)
            return pd.DataFrame(columns=["name", "UUID", "latitude", "longitude"])

    def get_branch_endpoints(self) -> pd.DataFrame:
        """Extract per-branch from/to bus UUIDs by resolving Arc references.

        Persisted at ingestion so downstream consumers (e.g. client
        extensions building transmission/transformer GeoJSON) don't
        need to re-read the system JSON. Without this table, the system
        JSON file path stored in `_gat_registry.scenarios.source_paths`
        becomes a hard dependency post-ingestion — and that path can be a
        temp upload directory that no longer exists.

        Returns columns: name, UUID, type, from_bus_uuid, to_bus_uuid.
        """
        empty = pd.DataFrame(columns=["name", "UUID", "type", "from_bus_uuid", "to_bus_uuid"])

        if "Arc" not in self._component_types:
            logger.warning("No Arc components — cannot derive branch endpoints")
            return empty

        try:
            arcs = self._parser.get_component("Arc", expand_ext=True)
        except Exception as e:
            logger.warning("Could not load Arc components: {}", e)
            return empty
        if arcs is None or len(arcs) == 0:
            return empty

        arcs = arcs.reset_index()

        def _ref_uuid(val: object) -> str:
            if isinstance(val, dict):
                return str(val.get("value", "") or val.get("uuid", ""))
            return str(val) if val is not None else ""

        arc_endpoints: dict[str, tuple[str, str]] = {}
        for _, row in arcs.iterrows():
            uuid_val = row.get("UUID")
            if not uuid_val:
                continue
            arc_endpoints[str(uuid_val)] = (_ref_uuid(row.get("from")), _ref_uuid(row.get("to")))

        records: list[dict[str, str]] = []
        # Include AreaInterchange even though it's not in _branch_types — it
        # has an arc and renders as a line in some scenarios.
        candidate_types = (self._branch_types | {"AreaInterchange"}) & self._component_types
        for ctype in candidate_types:
            try:
                df = self._parser.get_component(ctype, expand_ext=True)
            except Exception as e:
                logger.debug("Could not load {}: {}", ctype, e)
                continue
            if df is None or len(df) == 0:
                continue
            df = df.reset_index()
            for _, row in df.iterrows():
                arc_uuid = _ref_uuid(row.get("arc"))
                endpoints = arc_endpoints.get(arc_uuid)
                if not endpoints:
                    continue
                from_uuid, to_uuid = endpoints
                if not from_uuid or not to_uuid:
                    continue
                records.append({
                    "name": str(row.get("name", "")),
                    "UUID": str(row.get("UUID", "")),
                    "type": ctype,
                    "from_bus_uuid": from_uuid,
                    "to_bus_uuid": to_uuid,
                })

        result = pd.DataFrame.from_records(records, columns=empty.columns)
        logger.info(
            "Extracted {} branch endpoints across {} component types",
            len(result), result["type"].nunique() if len(result) else 0,
        )
        return result
