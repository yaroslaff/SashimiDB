# Exact configuration

## Environment variables

Env variables `EXACT_TOKEN` and `EXACT_TRUSTED_IP` (if preset) will be added to proper lists. `EXACT_IP_HEADER` will replace `ip_header` from config.

`EXACT_DATASET` to add new dataset from environment, format is  `datasetname:path/dataset.json datasetname2:https://example.com/dataset.json` or `datasetname:https://example.com/dataset.json` (no other dataset options are supported when loading dataset this way, default settings are used)

Environment variables automatically loaded from `.env` file.

## Global options

**limit** - default limit to datasets (if not overriden inside dataset configuration). If server-side limit is not set inside dataset configuration, this value used.

**datadir** - All JSON/YAML files from this directory is loaded to dataset with same name as filename (file "test.json" loaded as dataset "test"). Format of file is 

**origins** - list of allowed origins for CORS requests.  If `Origin` header in request matches one of origins given here, it's returned in `access-control-allow-origin` response header. Use `"*"` to enable all CORS requests

Example:
~~~
origins:
  - https://example.com/
~~~

## Dataset configuration
Example exact.yml:
~~~
datasets:
  dummy:
    url: https://dummyjson.com/products?limit=100
    keypath: 
      - products
    format: json
    limit: 5
    # Uncomment 'multiply' field to get 100*10K=1M records for bulk test
    # multiply: 1000
    postload:
      updesc: description.upper()
  contact:
    db: mysql://scott:tiger@127.0.0.1/contacts
    sql: SELECT * FROM contact
~~~
### Dataset loading

**url: URL** - dataset loaded from this URL

**file: PATH** - dataset loaded from this PATH

**db: DBURL** - dataset loaded from this db connection url (DBURL) , using SQL query specified in **sql** settings

### Dataset loading options

**format: FORMAT** - optional, yaml or json. If not given, format is guessed by filename/URL extension (JSON is default).

**postload_lower** - list of fields which must be converted to lowercase (Apple -> apple). Useful for case-insensitive search. 

**postload** - (dictionary) creates new field(s) for each record, based on given expression. For example, if postload has `updesc: description.lower()`, it will create field 'updesc' in each record, with lower-cased value of 'description' field. (almost as postload_lower, but to new field). Postload is much more flexible and allows to use nearly any python expression. (postload code is trusted, because it comes from admin)

**keypath** - Loads dataset from part of loaded document, like with https://dummyjson.com/products, URL returns complex data structure, and we load dataset from field 'products' of this dictionary.

**multiply** - Multiply loaded dataset N times (useful for testing). Note: new records will be exact copies of original, e.g. if you have one field with id=1 in original dataset of 1000 records, and used `multiply: 100`, you will get dataset with 100 000 records, and 100 of them will have id=1.

## Security options
Options related to security are documented in [SECURITY](SECURITY.md).
