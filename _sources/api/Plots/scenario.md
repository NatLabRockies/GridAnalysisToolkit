# Reporting Plots

High-level plots that take a `BaseScenario` (or subclass) and are
registered with the reporting framework via `@plot_function`. See
[Custom plots and the reporting framework](../../extending_plots.md) for
how the registration mechanism works and how to add your own.

## Registry

```{eval-rst}
.. automodule:: gat.registry
    :members:
    :exclude-members: plot_function
```

```{eval-rst}
.. autofunction:: gat.registry.plot_function
```

## Generation

```{eval-rst}
.. automodule:: gat.quickplots.generation_plots
    :members:
```

## System

```{eval-rst}
.. automodule:: gat.quickplots.system_plots
    :members:
```