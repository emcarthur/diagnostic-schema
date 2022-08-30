# README

- Author: Evonne McArthur
- Created 8/25/2022
- Last edited 8/29/2022

This readme is for the `diagnostic-schema` repo which hosts code for the diagnostic schema application Schematify available live here: http://diagnostic-schema.herokuapp.com/

This application is written in python using [Plotly Dash](https://plotly.com/dash/) (framework for building reactive web applications). It started out as a side project and is an ongoing work in progress (please forgive sloppy code).

## To do list of features/fixes for the application
- Modularize `app.py` into multiple scripts
- Provide better error support for google sheets URLs that are not public or that don't have the appropriate format
- Fix some kerning issues on pdf export, some indent issues on notes: https://forum.graphviz.org/t/unwanted-space-around-html-font-tags/460/4
- Add refresh button to top right
- Won't work with a node/sheet that starts with a number
- Left align node text if too long for one line
- Fix blurry thumbnail of youtube video
- Save url so it doesn't default to the hypoglycemia schema on refresh
- Fix disseapearing dashed lines
- Add text that can label edges (rather than nodes)

## Manifest

- `app.py` Contains all the code for the app and its interactivity
- `environment.yml`, `requirements.txt` - conda file to install dependencies and then cooresponding pipfile necessary for heroku
- `Procfile`, `runtime.txt` for heroku to appropriately run the app
- `./assets/` figures, images and favicon for app


