# Generate RTS-GMLC fixture data via Sienna for GAT regression tests.
#
# Usage:
#   julia --project=. generate.jl /output
#
# Env vars:
#   SIM_STEPS  — total simulation steps (24h each). Default: 7.
#   SIM_FILES  — produce N separate h5 files for testing the multi-file
#                aggregator path. Default: 1. When SIM_FILES=2, runs two
#                back-to-back sims with one step (24h) of overlap, writing
#                `simulation_store.h5` and `simulation_store_2.h5`. Each
#                sub-sim takes ceil(SIM_STEPS / 2) + 1 steps.
#
# Writes:
#   /output/sys.json                     — serialized PowerSystems system
#   /output/simulation_store.h5          — PowerSimulations results store
#   /output/simulation_store_2.h5        — (only when SIM_FILES=2)
#   /output/build.log                    — package versions + data_format_version
#
# Period: 7 days default. RTS-GMLC's standard 24h-with-12h-overlap day-ahead UC.

using Pkg
using Logging
using Dates

const OUTPUT_DIR = length(ARGS) > 0 ? ARGS[1] : "/output"
const SIM_STEPS = parse(Int, get(ENV, "SIM_STEPS", "7"))
# SIM_SYSTEM selects the fixture system: "rts" (default, RTS-GMLC — nodal
# detail, one week) or "pjm5" (PJM 5-bus, two synthetic zones, synthetic
# annual profiles — the long-horizon fixture; see repo issue #18).
const SIM_SYSTEM = get(ENV, "SIM_SYSTEM", "rts")
const SIM_FILES = parse(Int, get(ENV, "SIM_FILES", "1"))
const SIM_NAME = SIM_SYSTEM == "pjm5" ? "pjm5" : "rts_gmlc"

if !(SIM_FILES in (1, 2))
    error("SIM_FILES=$(SIM_FILES) not supported (expected 1 or 2)")
end

mkpath(OUTPUT_DIR)

# Log package versions for reproducibility / debugging mismatches.
open(joinpath(OUTPUT_DIR, "build.log"), "w") do io
    redirect_stdout(io) do
        Pkg.status()
    end
end

using Dates
using PowerSystems
using PowerSimulations
using PowerSystemCaseBuilder
using HiGHS
using JuMP

const PSY = PowerSystems
const PSI = PowerSimulations
const PSB = PowerSystemCaseBuilder

if SIM_SYSTEM == "pjm5"
    @info "Building PJM 5-bus system from PowerSystemCaseBuilder"
    sys_da = build_system(PSISystems, "c_sys5_pjm")

    # -- Two synthetic zones ------------------------------------------------
    # c_sys5_pjm ships with no Areas; split the five buses into two arbitrary
    # zones so area-level machinery (area dispatch, interchange, facets) has
    # something to exercise.
    z1 = Area("Z1")
    z2 = Area("Z2")
    add_component!(sys_da, z1)
    add_component!(sys_da, z2)
    buses = sort(collect(get_components(ACBus, sys_da)); by = get_number)
    for (i, b) in enumerate(buses)
        set_area!(b, i <= 2 ? z1 : z2)
    end
    @info "Assigned buses to zones" Z1 = [get_name(b) for b in buses[1:2]] Z2 = [get_name(b) for b in buses[3:end]]

    # -- Synthetic annual profiles ------------------------------------------
    # No 5-bus case ships more than ~a week of time series, so build 8760 h
    # of smooth deterministic profiles: a diurnal shape modulated seasonally
    # (winter + summer load peaks; solar by daylight; wind stronger at night
    # and in shoulder seasons). Attach as SingleTimeSeries and roll into
    # 48 h / 24 h forecast windows, mirroring the RTS DA structure.
    for T in (PSY.Deterministic, PSY.DeterministicSingleTimeSeries, PSY.SingleTimeSeries)
        try
            remove_time_series!(sys_da, T)
        catch
        end
    end

    ts_start = DateTime(2020, 1, 1)
    n_hours = 366 * 24   # 2020 is a leap year; keep full-year coverage + lookahead
    stamps = collect(range(ts_start; step = Hour(1), length = n_hours))

    hour_of(t) = Dates.hour(t)
    doy(t) = Dates.dayofyear(t)

    # Load: diurnal double-hump scaled by seasonal winter/summer peaking.
    load_shape(t) = begin
        h, d = hour_of(t), doy(t)
        diurnal = 0.72 + 0.18 * exp(-((h - 8.5)^2) / 8) + 0.28 * exp(-((h - 18.5)^2) / 10)
        seasonal = 0.82 + 0.18 * cos(2π * (d - 15) / 366)^2 + 0.14 * cos(2π * (d - 197) / 366)^2
        min(diurnal * seasonal, 1.0)
    end
    # Solar: daylight sinusoid, stronger in summer.
    solar_shape(t) = begin
        h, d = hour_of(t), doy(t)
        daylight = max(0.0, sin(π * (h - 6) / 12))
        daylight * (0.55 + 0.35 * sin(π * (d - 80) / 366)^2)
    end
    # Wind: stronger at night and in shoulder seasons.
    wind_shape(t) = begin
        h, d = hour_of(t), doy(t)
        diurnal = 0.55 + 0.25 * cos(π * (h - 3) / 12)
        seasonal = 0.6 + 0.3 * sin(2π * (d - 45) / 366)^2
        clamp(diurnal * seasonal, 0.05, 1.0)
    end

    # TimeSeries isn't a direct dep of this Project; reach it through PSY.
    TSD = PowerSystems.TimeSeries
    for load in get_components(PowerLoad, sys_da)
        ta = TSD.TimeArray(stamps, [load_shape(t) for t in stamps])
        add_time_series!(sys_da, load,
            PSY.SingleTimeSeries("max_active_power", ta;
                scaling_factor_multiplier = PSY.get_max_active_power))
    end
    for gen in get_components(RenewableDispatch, sys_da)
        shape = occursin("wind", lowercase(get_name(gen))) ? wind_shape : solar_shape
        ta = TSD.TimeArray(stamps, [shape(t) for t in stamps])
        add_time_series!(sys_da, gen,
            PSY.SingleTimeSeries("max_active_power", ta;
                scaling_factor_multiplier = PSY.get_max_active_power))
    end
    transform_single_time_series!(sys_da, Hour(48), Hour(24))
    @info "Attached synthetic annual profiles" n_hours windows = PSY.get_forecast_window_count(sys_da)
else
    @info "Building RTS-GMLC system from PowerSystemCaseBuilder"
    sys_da = build_system(PSISystems, "modified_RTS_GMLC_DA_sys")

    # PowerSimulations 0.30 split hydro into a separate package; RTS-GMLC ships
    # only one HydroDispatch unit and we don\'t need it for a fixture baseline.
    for h in collect(get_components(HydroDispatch, sys_da))
        @info "Removing hydro component $(get_name(h)) (out-of-scope for fixture)"
        remove_component!(sys_da, h)
    end
end

@info "Serializing system → sys.json"
to_json(sys_da, joinpath(OUTPUT_DIR, "sys.json"); force=true)

# Capture data_format_version from the serialized JSON so the build log shows it.
let
    raw = read(joinpath(OUTPUT_DIR, "sys.json"), String)
    m = match(r"\"data_format_version\"\s*:\s*\"([^\"]+)\"", raw)
    open(joinpath(OUTPUT_DIR, "build.log"), "a") do io
        println(io, "\ndata_format_version: ", m === nothing ? "UNKNOWN" : m.captures[1])
    end
end

@info "Configuring UC template"
template_uc = ProblemTemplate(NetworkModel(DCPPowerModel; use_slacks = true))
set_device_model!(template_uc, ThermalStandard, ThermalStandardUnitCommitment)
set_device_model!(template_uc, RenewableDispatch, RenewableFullDispatch)
set_device_model!(template_uc, RenewableNonDispatch, FixedOutput)
set_device_model!(template_uc, PowerLoad, StaticPowerLoad)
set_device_model!(template_uc, Line, StaticBranch)
if SIM_SYSTEM == "rts"
    set_service_model!(template_uc, VariableReserve{ReserveUp}, RangeReserve)
    set_service_model!(template_uc, VariableReserve{ReserveDown}, RangeReserve)
end

# ED template runs on the same DA system at the system's native time-series
# resolution (1h for RTS-GMLC DA). Using sys_da rather than sys_rt keeps the
# fixture small while still exercising:
#   * The within-file block-overlap dedup logic — each ED step covers a
#     lookahead horizon, so consecutive solves overlap.
#   * The cross-decision-model UC→ED feedforward (commitments propagate
#     from UC into ED via SemiContinuousFeedforward).
@info "Configuring ED template"
template_ed = ProblemTemplate(NetworkModel(DCPPowerModel; use_slacks = true))
set_device_model!(template_ed, ThermalStandard, ThermalStandardDispatch)
set_device_model!(template_ed, RenewableDispatch, RenewableFullDispatch)
set_device_model!(template_ed, RenewableNonDispatch, FixedOutput)
set_device_model!(template_ed, PowerLoad, StaticPowerLoad)
set_device_model!(template_ed, Line, StaticBranch)
if SIM_SYSTEM == "rts"
    set_service_model!(template_ed, VariableReserve{ReserveUp}, RangeReserve)
    set_service_model!(template_ed, VariableReserve{ReserveDown}, RangeReserve)
end

solver = optimizer_with_attributes(
    HiGHS.Optimizer,
    "mip_rel_gap" => 0.01,
    "log_to_console" => false,
)

models = SimulationModels(
    decision_models = [
        DecisionModel(template_uc, sys_da; name="UC", optimizer=solver),
        DecisionModel(template_ed, sys_da; name="ED", optimizer=solver),
    ],
)

# UC commitments feed forward into ED as binary semi-continuous bounds on
# ThermalStandard active power. Standard PSI two-stage pattern.
sequence = SimulationSequence(
    models = models,
    feedforwards = Dict(
        "ED" => [
            SemiContinuousFeedforward(
                component_type = ThermalStandard,
                source = OnVariable,
                affected_values = [ActivePowerVariable],
            ),
        ],
    ),
    ini_cond_chronology = InterProblemChronology(),
)

"""
Run one PSI simulation block and copy its results h5 to `dst_filename`
inside `OUTPUT_DIR`. The PSI scratch dir (`<OUTPUT_DIR>/<sim_name>/`)
is removed afterwards so only the canonical h5 remains.
"""
function run_one_sim(sim_name::String, steps::Int, initial_time, dst_filename::String)
    @info "Building simulation '$(sim_name)': $(steps) steps, initial_time=$(initial_time)"
    sim = Simulation(
        name = sim_name,
        steps = steps,
        models = models,
        sequence = sequence,
        simulation_folder = OUTPUT_DIR,
        initial_time = initial_time,
    )
    build!(sim, console_level=Logging.Info, file_level=Logging.Debug)
    @info "Executing simulation '$(sim_name)'"
    execute!(sim, enable_progress_bar=false)

    src = joinpath(OUTPUT_DIR, sim_name, "data_store", "simulation_store.h5")
    isfile(src) || error("simulation_store.h5 not found at expected path: $src")
    dst = joinpath(OUTPUT_DIR, dst_filename)
    @info "Copying $src → $dst"
    cp(src, dst; force=true)
    rm(joinpath(OUTPUT_DIR, sim_name); recursive=true)
end

if SIM_FILES == 1
    run_one_sim(SIM_NAME, SIM_STEPS, nothing, "simulation_store.h5")
else
    # Two-file mode. Split SIM_STEPS into two overlapping sub-simulations
    # so we exercise the multi-file aggregation path. The output h5s have
    # one step (24h) of overlap, which the aggregator's dedup logic should
    # collapse on read.
    #
    # Step layout (default SIM_STEPS=7):
    #   sub1: ceil(7/2)+0 = 4 steps starting at the system's first
    #         time-series timestamp
    #   sub2: 4 steps starting 1 step before sub1 ends → overlaps by 1
    half_steps = cld(SIM_STEPS, 2)
    sub1_steps = half_steps + 1   # +1 so the overlap is real, not an off-by-one
    sub2_steps = SIM_STEPS - half_steps + 1

    # RTS-GMLC's modified_RTS_GMLC_DA_sys time series starts at
    # 2020-01-01 00:00:00. This script is purpose-built for that case;
    # if you swap the system, update this constant.
    sub1_start = DateTime(2020, 1, 1, 0, 0, 0)
    # Each step is 24h, so sub2 starts (sub1_steps - 1) days after sub1's
    # start to give a 1-step (24h) overlap.
    sub2_start = sub1_start + Day(sub1_steps - 1)

    @info "SIM_FILES=2: sub1=$(sub1_steps) steps from $(sub1_start), sub2=$(sub2_steps) steps from $(sub2_start)"

    run_one_sim("$(SIM_NAME)_1", sub1_steps, sub1_start, "simulation_store.h5")
    run_one_sim("$(SIM_NAME)_2", sub2_steps, sub2_start, "simulation_store_2.h5")
end

@info "Done. Outputs in $OUTPUT_DIR"
