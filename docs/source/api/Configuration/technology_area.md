# Updating Technology and Area Relationships

It is often the case that we need to translate from generation types defined in a model to our own simplified types.

This can be updated through the object properties as follows.

<pre class="brush: python">

sobj = SiennaScenario(/path/to/system_file, /path/to/simulation_file)

#update the
sobj._tech_simple(
    {
        PV: Solar,
        WT: Wind,
        NG: Natural Gas,
        ....
    }
)

#update the generator->area mapping and load->area mapping
sobj._gen_area_map({
    generator-pv1: Area1,
    generator-pv2: Area2,
    ....

})

sobj._load_area_map({
    load-bus1: Area1,
    load-bus2: Area2,
    ...
})

</pre>