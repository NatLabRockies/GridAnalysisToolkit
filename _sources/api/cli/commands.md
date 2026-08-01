# GAT Command Line Interface

GAT includes a command line interface for running reports against configuration files with overrides.


## Example Run
Runs the system comparison report based on two configuration files, overrides the display name with new names, and applies a filter to consider p61 and p62 as the whole "System". You can also override
the s1 and s2 system files with new paths but keeping the rest of the scenario configuations. This will write the results to the **test_output** directory.

```bash
gat run multi --s1-config=/path/to/reeds_config.yaml --s2-config=/path/to/sienna_config.yaml --s1-name=reeds_2030 --s2-name=sienna_2030 --area-filter="p61,p62" --output-path=test_output
```

## Example Init and Run
You can also initialize the global configuration for the report using the init command.

```bash
gat init multi --s1-config=/path/to/reeds_config.yaml --s2-config=/path/to/sienna_config.yaml --s1-name=reeds_2030 --s2-name=sienna_2030 --area-filter="p61,p62"
```

You can then run against the report config and override the parameters for --{s1/s2}-{config,path,name}.

```bash
gat run multi --report-config=comparison_report_config.yaml
```

## Command Reference

```{eval-rst}
.. click:: gat.cli:cli
   :prog: gat
   :nested: full
```