# Color Configuration


## Option 1 - Using the Default Color Map

The simplest solution is to map your generation types to types found in the GAT quickplots colormap.

`qp.get_colormap().keys()`

You would then update your Scenario Object to have

<pre>
<code>
sobj = SiennaScenario(/path/to/system_file, /path/to/simulation_file)
</code>
<code>
sobj._tech_simple = {battery_2hr: Battery, battery_4hr: Battery}
</code>
</pre>

## Option 2 - Custom Color Maps

You can also define a new color scheme yourself and pass a dictionary of simplified technologies to the *.set_colormap()* function.

`qp.set_colormap(new_colormap)`