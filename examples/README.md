# Examples
To make everything easier, [pyenv](https://github.com/pyenv/pyenv) helps manage multiple Python versions 
and optionally virtualenvs with [pyenv-virtualenv](https://github.com/pyenv/pyenv-virtualenv).

No matter if you choose to use pyenv or not, you should create virtual environments for each example 
you wish to run. Then, you should install the requirements for that example inside the virtual env 
by running: `pip install -r requirements.txt`.

The above is required for all examples.

Example for sample-plain using pyenv:
```shell script
# switch to example directory
cd ./sample-plain
# create the virtual environment using Python 3.6
pyenv virtualenv -p python3.6 starlette-jsonapi-plain
# activate the virtual environment
pyenv activate starlette-jsonapi-plain
# install dependencies specific to each project
pip install -r requirements.txt
python start_service.py
```
You can then access [users](http://127.0.0.1:8000/api/users/) and [organizations](http://127.0.0.1:8000/api/organizations/).

## 1. sample-plain

Contains a basic implementation of 2 resources, `users` and `organizations` using plain Python classes.

#### Running:
In order to start the service on http://127.0.0.1:8000/, you can run:
`python start_service.py`



## 2. sample-tortoise-orm
    
Contains a basic implementation of 2 resources, `users` and `organizations` using tortoise-orm with a PostgreSQL database.

#### Running:
You should start the PostgreSQL database first, by running: `docker-compose up -d`

Then you can start the service on http://127.0.0.1:8000/, by running:
`python start_service.py`


## Client:
After starting one of the services, you can play around in [Postman](https://www.postman.com/) using the included 
[collection](starlette_jsonapi_client_example.postman_collection.json).
