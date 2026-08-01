# Multi-Scenario Objects

The purpose of the MultiScenario object is to facilitate data management across a multitude of scenarios while maintaining the familiar BaseScenario api. The primary difference being that an additional
index level is added to each output frame.

## Use Cases
This object is particularly useful in the following situations:

- Comparing a translation from a Capacity Expansion Model to a Production Cost Model using a tool like R2X
- Comparing multiple simulation runs of the same Production Cost Model with slight changes like N-m contingency analysis, or techno-economic tradeoff analysis.

## Recommendations
It is recommended that individual Scenario Objects share a common TechnologyMapping and Area set. This way the data returned is well aligned for comparisons. For multi-year scenarios of the same/similar model,
it is recommended to use a single scenario object and aggregate across multiple years by passing multiple simulation files representing those years.

## Initializing a MultiScenario Object


```python
from gat.scenariohandlers import MultiScenario

# the keys will override the display_name of each scenario.
ms = MultiScenario({"reeds":reeds_scenario, "sienna":sienna_scenario})

ms.get_generation_capacity() # returns capacity by area
```


## Option 2
```python
from gat.scenariohandler import MultiScenario

ms = MultiScenario()
ms.add_scenario("reeds", rscen2)
```

## API

```{eval-rst}
.. automodule:: gat.scenariohandlers.multi
    :members:
```