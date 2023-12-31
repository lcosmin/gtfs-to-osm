# Intro

This repo contains a Jupyter notebook which provides a visual way for correlating public transport stops from GTFS data with those from Openstreetmap data, with the purpose of adding missing GTFS information to Openstreetmap. 

In its current state, the notebook only writes a CSV file containing correlation data: `gtfs:stop_id`, `gtfs:stop_name`, `osm:id` and `osm:name`. 

# Installation

## Install [poetry](https://python-poetry.org/) 

```bash
$ pip install --user poetry 
``` 

Might need to re-login; if the `poetry` binary is not available, make sure `$HOME/.local/bin` is added to your $PATH.


## Clone the repository

```bash
$ git clone https://github.com/lcosmin/gtfs-to-osm.git
```

## Create python virtual environment and install dependencies

```bash
$ cd gtfs-to-osm
$ poetry install
```

## Open a shell with the virtual environment activated

```bash
$ poetry shell
```

## Start Jupyter Lab

```bash
$ jupyter-lab --ip <local-ip> --port 8888
```

The `--ip` and `--port` parameters can be omitted, in which case Jupyter will start up on 127.0.0.1:8888. 

When starting, it will attempt to open a browser and go to its start page. This won't be possible if running remotely and a similar message can be seen:

```
[I 2023-07-01 18:12:00.617 ServerApp] Jupyter Server 2.7.0 is running at:
[I 2023-07-01 18:12:00.617 ServerApp] http://172.18.207.77:8888/lab?token=1e5fd4dee339ede326c78ee1f9e4b9de66a7c588c9853546
[I 2023-07-01 18:12:00.617 ServerApp]     http://127.0.0.1:8888/lab?token=1e5fd4dee339ede326c78ee1f9e4b9de66a7c588c9853546
[I 2023-07-01 18:12:00.617 ServerApp] Use Control-C to stop this server and shut down all kernels (twice to skip confirmation).
[W 2023-07-01 18:12:01.320 ServerApp] No web browser found: Error('could not locate runnable browser').
[C 2023-07-01 18:12:01.321 ServerApp]

    To access the server, open this file in a browser:
        file:///home/user/.local/share/jupyter/runtime/jpserver-2880-open.html
    Or copy and paste one of these URLs:
        http://172.18.207.77:8888/lab?token=1e5fd4dee339ede326c78ee1f9e4b9de66a7c588c9853546
        http://127.0.0.1:8888/lab?token=1e5fd4dee339ede326c78ee1f9e4b9de66a7c588c9853546
```

Notice the link at the bottom for accessing Jupyter (use the one with the IP address you specified).

## Get the required data

### GTFS data

You'll need a zip file in the standard GTFS static format, containing the bus stops you want to process. 

For Bucharest, you can get it [here](https://gtfs.tpbi.ro/regional/).

### Openstreetmap data

Use [overpass](https://overpass-turbo.eu/) and run this query on the region you want:

```
/*
This has been generated by the overpass-turbo wizard.
The original search was:
“public_transport=platform”
*/
[out:json][timeout:25];
// gather results
(
  // query part for: “public_transport=platform”
  node["public_transport"="platform"]({{bbox}});
  way["public_transport"="platform"]({{bbox}});
  relation["public_transport"="platform"]({{bbox}});
);
// print results
out body;
>;
out skel qt;
```

Download the resulting RAW data (JSON file).

> **_NOTE:_** The downloaded .zip(s) and .json(s) can be placed in the `data/` directory of this repo.

# Usage

Open the browser and connect to Jupyter. You should see the `gtfs-to-osm.ipynb` notebook in the file browser.

Double click to open it.

The notebook must be trusted first:  `View` -> `Activate Command Palette` -> `Trust Notebook`.

Edit the data in the first cell and set the variables:

* `GTFS_FILE` should point to the zip containing your GTFS data (e.g. `./data/gtfs.zip`)
* `OSM_FILE` should point to the json containing data extracted from OSM (using overpass)
* `OUTPUT_FILE` is the CSV file where correlations should be written
* `FILTER_ALREADY_CORRELATED_DATA` - set to `True` if already correlated data should not be displayed anymore (on startup)
